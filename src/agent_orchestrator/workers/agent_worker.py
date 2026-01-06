"""Agent worker for processing tasks from the queue."""

import asyncio
import signal
from typing import Any
from uuid import UUID

import structlog

from agent_orchestrator.config import Settings
from agent_orchestrator.core.agents import AgentDefinition, AgentInstance, AgentStatus, ModelConfig, ModelProvider
from agent_orchestrator.core.agents.runtime import AgentRuntime, AgentRuntimeFactory
from agent_orchestrator.core.agents.tools import ToolRegistry, create_builtin_tools
from agent_orchestrator.core.workflows import Task, TaskStatus
from agent_orchestrator.infrastructure.cache.redis_client import RedisClient, get_redis_client
from agent_orchestrator.infrastructure.llm import get_llm_client
from agent_orchestrator.infrastructure.messaging.nats_client import NATSClient, get_nats_client

logger = structlog.get_logger(__name__)


class AgentWorker:
    """
    Worker process for executing agent tasks.

    Subscribes to task queues and executes tasks using agent runtimes.
    """

    def __init__(
        self,
        worker_id: str,
        settings: Settings,
        concurrency: int = 5,
    ) -> None:
        self._worker_id = worker_id
        self._settings = settings
        self._concurrency = concurrency
        self._running = False
        self._nats: NATSClient | None = None
        self._redis: RedisClient | None = None
        self._agents: dict[UUID, AgentRuntime] = {}
        self._active_tasks: dict[UUID, asyncio.Task[Any]] = {}
        self._semaphore = asyncio.Semaphore(concurrency)

    async def start(self) -> None:
        """Start the worker."""
        logger.info(
            "Starting agent worker",
            worker_id=self._worker_id,
            concurrency=self._concurrency,
        )

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Initialize connections
        self._nats = await get_nats_client(self._settings.nats)
        self._redis = await get_redis_client(self._settings.redis)

        # Initialize tool registry
        tool_registry = ToolRegistry()
        for tool in create_builtin_tools():
            tool_registry.register(tool)

        # Initialize LLM client
        llm_client = get_llm_client(self._settings.llm)

        # Create runtime factory
        self._runtime_factory = AgentRuntimeFactory(llm_client, tool_registry)

        # Subscribe to task queue
        self._running = True
        await self._nats.subscribe(
            "TASKS.created",
            queue=f"workers-{self._worker_id}",
            handler=self._handle_task,
            durable=f"worker-{self._worker_id}",
        )

        # Subscribe to agent commands
        await self._nats.subscribe(
            "AGENTS.commands.*",
            queue=f"workers-{self._worker_id}",
            handler=self._handle_agent_command,
            durable=f"worker-commands-{self._worker_id}",
        )

        logger.info("Agent worker started", worker_id=self._worker_id)

        # Keep running
        while self._running:
            await asyncio.sleep(1)
            await self._send_heartbeat()

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        logger.info("Stopping agent worker", worker_id=self._worker_id)
        self._running = False

        # Wait for active tasks to complete
        if self._active_tasks:
            logger.info(
                "Waiting for active tasks",
                count=len(self._active_tasks),
            )
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)

        # Close connections
        if self._nats:
            await self._nats.close()
        if self._redis:
            await self._redis.close()

        logger.info("Agent worker stopped", worker_id=self._worker_id)

    async def _handle_task(self, data: dict[str, Any]) -> None:
        """Handle incoming task."""
        task_id = UUID(data["task_id"])

        logger.info(
            "Received task",
            task_id=str(task_id),
            name=data.get("name"),
        )

        # Acquire semaphore to limit concurrency
        async with self._semaphore:
            try:
                await self._execute_task(data)
            except Exception as e:
                logger.exception(
                    "Task execution failed",
                    task_id=str(task_id),
                    error=str(e),
                )
                await self._publish_task_failed(task_id, str(e))

    async def _execute_task(self, data: dict[str, Any]) -> None:
        """Execute a task."""
        task_id = UUID(data["task_id"])

        # Create task object
        task = Task(
            task_id=task_id,
            name=data["name"],
            description=data.get("description", ""),
            input_data=data.get("input_data", {}),
            required_capabilities=set(data.get("required_capabilities", [])),
            timeout_seconds=data.get("timeout_seconds", 300),
        )

        # Get agent_id from task data (set by conversations or task API)
        agent_id = UUID(data["agent_id"]) if data.get("agent_id") else None

        # Get or create agent runtime
        agent = await self._get_or_create_agent(task, agent_id=agent_id)
        if not agent:
            await self._publish_task_failed(
                task_id, "No suitable agent available"
            )
            return

        # Publish task started event
        await self._publish_task_started(task_id, agent.agent_id)

        # Execute task
        task_input = task.description
        if task.input_data:
            task_input += f"\n\nInput data: {task.input_data}"

        result = await agent.execute_task(
            task_id=task_id,
            task_input=task_input,
            context=task.input_data,
        )

        if result.success:
            await self._publish_task_completed(task_id, result.result, agent.agent_id)
        else:
            await self._publish_task_failed(task_id, result.error or "Unknown error")

    async def _get_or_create_agent(
        self, task: Task, agent_id: UUID | None = None
    ) -> AgentRuntime | None:
        """Get or create an agent runtime for the task."""
        # Try to load agent from Redis if agent_id is provided
        if agent_id and self._redis:
            agent_data = await self._redis.get(f"agent:{agent_id}")
            if agent_data:
                # Build AgentDefinition from stored data
                llm_config_data = agent_data.get("llm_config", {})
                definition = AgentDefinition(
                    agent_id=UUID(agent_data["agent_id"]),
                    name=agent_data["name"],
                    role=agent_data["role"],
                    goal=agent_data["goal"],
                    backstory=agent_data.get("backstory"),
                    llm_config=ModelConfig(
                        provider=llm_config_data.get("provider", "anthropic"),
                        model_id=llm_config_data.get("model_id", "claude-sonnet-4-20250514"),
                        temperature=llm_config_data.get("temperature", 0.7),
                        max_tokens=llm_config_data.get("max_tokens", 4096),
                    ),
                    capabilities=set(agent_data.get("capabilities", [])),
                )

                logger.info(
                    "Loaded agent from Redis",
                    agent_id=str(agent_id),
                    name=definition.name,
                    model=definition.llm_config.model_id,
                )

                return self._runtime_factory.create(
                    definition=definition,
                    event_handler=self._handle_agent_event,
                )

        # Fallback: create a default agent if no agent_id or not found
        logger.warning(
            "Using default agent - no agent_id provided or agent not found",
            agent_id=str(agent_id) if agent_id else None,
        )
        # Use settings for default LLM config
        default_llm_config = ModelConfig(
            provider=ModelProvider(self._settings.llm.default_provider),
            model_id=self._settings.llm.default_model,
        )
        definition = AgentDefinition(
            name="Worker Agent",
            role="General purpose task executor",
            goal="Complete the assigned task efficiently and accurately",
            capabilities=task.required_capabilities,
            llm_config=default_llm_config,
        )

        return self._runtime_factory.create(
            definition=definition,
            event_handler=self._handle_agent_event,
        )

    async def _handle_agent_command(self, data: dict[str, Any]) -> None:
        """Handle agent commands."""
        command = data.get("command")
        agent_id = data.get("agent_id")

        logger.debug(
            "Received agent command",
            command=command,
            agent_id=agent_id,
        )

        if command == "stop":
            if agent_id and agent_id in self._agents:
                await self._agents[agent_id].stop(graceful=data.get("graceful", True))

    async def _handle_agent_event(self, event: Any) -> None:
        """Handle events from agent execution."""
        if self._nats:
            try:
                await self._nats.publish(
                    f"AGENTS.events.{event.event_type.value}",
                    event.model_dump(mode="json"),
                )
            except Exception as e:
                # Don't let event publishing failures crash task execution
                logger.warning(
                    "Failed to publish agent event",
                    event_type=event.event_type.value,
                    error=str(e),
                )

    async def _publish_task_started(
        self,
        task_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Publish task started event."""
        if self._nats:
            await self._nats.publish(
                "TASKS.started",
                {
                    "task_id": str(task_id),
                    "worker_id": self._worker_id,
                    "agent_id": str(agent_id),
                },
            )

    async def _publish_task_completed(
        self,
        task_id: UUID,
        result: Any,
        agent_id: UUID | None = None,
    ) -> None:
        """Publish task completed event."""
        if self._nats:
            await self._nats.publish(
                "RESULTS.completed",
                {
                    "task_id": str(task_id),
                    "worker_id": self._worker_id,
                    "agent_id": str(agent_id) if agent_id else None,
                    "result": result,
                },
            )

    async def _publish_task_failed(
        self,
        task_id: UUID,
        error: str,
    ) -> None:
        """Publish task failed event."""
        if self._nats:
            await self._nats.publish(
                "RESULTS.failed",
                {
                    "task_id": str(task_id),
                    "worker_id": self._worker_id,
                    "error": error,
                },
            )

    async def _send_heartbeat(self) -> None:
        """Send worker heartbeat."""
        if self._nats:
            await self._nats.publish(
                "WORKERS.heartbeat",
                {
                    "worker_id": self._worker_id,
                    "active_tasks": len(self._active_tasks),
                    "capacity": self._concurrency - len(self._active_tasks),
                },
            )
