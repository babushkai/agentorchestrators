"""Main orchestrator for task routing and agent management."""

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog

from agent_orchestrator.core.agents import AgentDefinition, AgentInstance, AgentStatus
from agent_orchestrator.core.events import TaskEvent
from agent_orchestrator.core.workflows import Task, TaskPriority, TaskStatus

logger = structlog.get_logger(__name__)


class TaskQueue:
    """Priority queue for tasks."""

    def __init__(self) -> None:
        self._queues: dict[TaskPriority, asyncio.Queue[Task]] = {
            priority: asyncio.Queue() for priority in TaskPriority
        }

    async def put(self, task: Task) -> None:
        """Add a task to the queue."""
        await self._queues[task.priority].put(task)

    async def get(self, timeout: float = 1.0) -> Task | None:
        """Get the highest priority task."""
        for priority in reversed(TaskPriority):
            queue = self._queues[priority]
            try:
                return queue.get_nowait()
            except asyncio.QueueEmpty:
                continue
        return None

    def qsize(self) -> int:
        """Get total queue size across all priorities."""
        return sum(q.qsize() for q in self._queues.values())


class Orchestrator:
    """
    Main orchestrator for distributed agent coordination.

    Responsibilities:
    - Task routing and load balancing
    - Agent registration and discovery
    - Priority queue management
    - Capability-based matching
    """

    def __init__(
        self,
        event_publisher: Callable[[Any], Any] | None = None,
    ) -> None:
        self._task_queue = TaskQueue()
        self._agents: dict[UUID, AgentInstance] = {}
        self._agent_definitions: dict[UUID, AgentDefinition] = {}
        self._pending_tasks: dict[UUID, Task] = {}
        self._event_publisher = event_publisher
        self._running = False
        self._dispatch_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the orchestrator."""
        logger.info("Starting orchestrator")
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())

    async def stop(self) -> None:
        """Stop the orchestrator."""
        logger.info("Stopping orchestrator")
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

    async def register_agent(
        self,
        definition: AgentDefinition,
    ) -> AgentInstance:
        """Register a new agent."""
        instance = AgentInstance(
            agent_definition_id=definition.agent_id,
            status=AgentStatus.IDLE,
            started_at=datetime.now(timezone.utc),
        )

        self._agent_definitions[definition.agent_id] = definition
        self._agents[instance.instance_id] = instance

        logger.info(
            "Agent registered",
            agent_id=str(definition.agent_id),
            instance_id=str(instance.instance_id),
            capabilities=list(definition.capabilities),
        )

        return instance

    async def unregister_agent(self, instance_id: UUID) -> None:
        """Unregister an agent."""
        instance = self._agents.pop(instance_id, None)
        if instance:
            logger.info(
                "Agent unregistered",
                instance_id=str(instance_id),
            )

    async def submit_task(self, task: Task) -> None:
        """Submit a task for execution."""
        task.status = TaskStatus.QUEUED
        self._pending_tasks[task.task_id] = task
        await self._task_queue.put(task)

        logger.info(
            "Task submitted",
            task_id=str(task.task_id),
            name=task.name,
            priority=task.priority.name,
        )

        if self._event_publisher:
            await self._event_publisher(
                TaskEvent.created(
                    task_id=task.task_id,
                    name=task.name,
                    description=task.description,
                    input_data=task.input_data,
                    tenant_id=task.tenant_id,
                )
            )

    async def _dispatch_loop(self) -> None:
        """Main dispatch loop for routing tasks to agents."""
        while self._running:
            try:
                task = await self._task_queue.get()
                if task is None:
                    await asyncio.sleep(0.1)
                    continue

                # Find suitable agent
                agent = await self._find_agent(task)
                if agent:
                    await self._assign_task(task, agent)
                else:
                    # No available agent, requeue
                    await self._task_queue.put(task)
                    await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Dispatch error", error=str(e))
                await asyncio.sleep(1)

    async def _find_agent(self, task: Task) -> AgentInstance | None:
        """Find a suitable agent for a task."""
        candidates: list[AgentInstance] = []

        for instance in self._agents.values():
            if not instance.is_available():
                continue

            definition = self._agent_definitions.get(instance.agent_definition_id)
            if not definition:
                continue

            # Check capability match
            if task.required_capabilities:
                if not task.required_capabilities.issubset(definition.capabilities):
                    continue

            candidates.append(instance)

        if not candidates:
            return None

        # Select agent with best performance (lowest avg execution time)
        candidates.sort(
            key=lambda a: (
                a.total_execution_time_ms / max(a.tasks_completed, 1)
                if a.tasks_completed > 0
                else float("inf")
            )
        )

        return candidates[0]

    async def _assign_task(
        self,
        task: Task,
        agent: AgentInstance,
    ) -> None:
        """Assign a task to an agent."""
        task.status = TaskStatus.ASSIGNED
        task.assigned_agent_id = agent.agent_definition_id
        agent.current_task_id = task.task_id
        agent.status = AgentStatus.RUNNING

        logger.info(
            "Task assigned",
            task_id=str(task.task_id),
            agent_id=str(agent.agent_definition_id),
            instance_id=str(agent.instance_id),
        )

        if self._event_publisher:
            await self._event_publisher(
                TaskEvent.assigned(
                    task_id=task.task_id,
                    agent_id=agent.agent_definition_id,
                    tenant_id=task.tenant_id,
                )
            )

    async def complete_task(
        self,
        task_id: UUID,
        result: dict[str, Any],
    ) -> None:
        """Mark a task as completed."""
        task = self._pending_tasks.pop(task_id, None)
        if not task:
            logger.warning("Task not found", task_id=str(task_id))
            return

        task.complete(result)

        # Update agent state
        for agent in self._agents.values():
            if agent.current_task_id == task_id:
                agent.current_task_id = None
                agent.status = AgentStatus.IDLE
                agent.tasks_completed += 1
                break

        logger.info(
            "Task completed",
            task_id=str(task_id),
        )

        if self._event_publisher:
            await self._event_publisher(
                TaskEvent.completed(
                    task_id=task_id,
                    result=result,
                    tenant_id=task.tenant_id,
                )
            )

    async def fail_task(
        self,
        task_id: UUID,
        error: str,
    ) -> None:
        """Mark a task as failed."""
        task = self._pending_tasks.get(task_id)
        if not task:
            return

        task.fail(error)

        # Update agent state
        for agent in self._agents.values():
            if agent.current_task_id == task_id:
                agent.current_task_id = None
                agent.status = AgentStatus.IDLE
                agent.tasks_failed += 1
                break

        # Check if task can be retried
        if task.can_retry():
            task.retry_count += 1
            task.status = TaskStatus.PENDING
            await self._task_queue.put(task)
            logger.info(
                "Task requeued for retry",
                task_id=str(task_id),
                retry=task.retry_count,
            )
        else:
            self._pending_tasks.pop(task_id, None)
            logger.error(
                "Task failed permanently",
                task_id=str(task_id),
                error=error,
            )

            if self._event_publisher:
                await self._event_publisher(
                    TaskEvent.failed(
                        task_id=task_id,
                        error=error,
                        tenant_id=task.tenant_id,
                    )
                )

    def get_metrics(self) -> dict[str, Any]:
        """Get orchestrator metrics."""
        active_agents = sum(
            1 for a in self._agents.values() if a.status == AgentStatus.RUNNING
        )
        idle_agents = sum(
            1 for a in self._agents.values() if a.status == AgentStatus.IDLE
        )

        return {
            "queue_depth": self._task_queue.qsize(),
            "pending_tasks": len(self._pending_tasks),
            "total_agents": len(self._agents),
            "active_agents": active_agents,
            "idle_agents": idle_agents,
        }
