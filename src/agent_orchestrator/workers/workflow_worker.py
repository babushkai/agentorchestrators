"""Workflow worker for processing workflow executions."""

import asyncio
import signal
from typing import Any
from uuid import UUID

import structlog

from agent_orchestrator.config import Settings
from agent_orchestrator.core.workflows import WorkflowDefinition, WorkflowExecution, WorkflowStatus
from agent_orchestrator.core.workflows.engine import WorkflowEngine
from agent_orchestrator.infrastructure.cache.redis_client import RedisClient, get_redis_client
from agent_orchestrator.infrastructure.messaging.nats_client import NATSClient, get_nats_client

logger = structlog.get_logger(__name__)


class MockTaskExecutor:
    """Task executor that publishes tasks to the message broker."""

    def __init__(self, nats: NATSClient) -> None:
        self._nats = nats
        self._pending_results: dict[UUID, asyncio.Future[dict]] = {}

    async def execute(self, task: Any) -> dict[str, Any]:
        """Execute a task by publishing it and waiting for result."""
        from agent_orchestrator.core.workflows import Task

        if not isinstance(task, Task):
            raise ValueError("Expected Task object")

        # Create a future for the result
        future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        self._pending_results[task.task_id] = future

        # Publish task
        await self._nats.publish(
            "TASKS.created",
            {
                "task_id": str(task.task_id),
                "name": task.name,
                "description": task.description,
                "input_data": task.input_data,
                "required_capabilities": list(task.required_capabilities),
                "priority": task.priority.value,
                "timeout_seconds": task.timeout_seconds,
                "parent_workflow_id": str(task.parent_workflow_id) if task.parent_workflow_id else None,
                "parent_step_id": task.parent_step_id,
            },
        )

        try:
            # Wait for result with timeout
            result = await asyncio.wait_for(future, timeout=task.timeout_seconds)
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Task {task.task_id} timed out")
        finally:
            self._pending_results.pop(task.task_id, None)

    async def handle_result(self, data: dict[str, Any]) -> None:
        """Handle task result from message broker."""
        task_id = UUID(data["task_id"])
        future = self._pending_results.get(task_id)

        if future and not future.done():
            if "error" in data:
                future.set_exception(Exception(data["error"]))
            else:
                future.set_result(data.get("result", {}))


class WorkflowWorker:
    """
    Worker process for executing workflows.

    Subscribes to workflow execution events and runs the workflow engine.
    """

    def __init__(
        self,
        worker_id: str,
        settings: Settings,
    ) -> None:
        self._worker_id = worker_id
        self._settings = settings
        self._running = False
        self._nats: NATSClient | None = None
        self._redis: RedisClient | None = None
        self._active_executions: dict[UUID, asyncio.Task[Any]] = {}

    async def start(self) -> None:
        """Start the workflow worker."""
        logger.info(
            "Starting workflow worker",
            worker_id=self._worker_id,
        )

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Initialize connections
        self._nats = await get_nats_client(self._settings.nats)
        self._redis = await get_redis_client(self._settings.redis)

        # Create task executor and workflow engine
        self._task_executor = MockTaskExecutor(self._nats)
        self._workflow_engine = WorkflowEngine(
            task_executor=self._task_executor,
            event_publisher=self._publish_event,
        )

        # Subscribe to workflow execution events
        self._running = True
        await self._nats.subscribe(
            "WORKFLOWS.execution.started",
            queue=f"workflow-workers",
            handler=self._handle_execution_start,
            durable=f"workflow-worker-{self._worker_id}",
        )

        # Subscribe to task results
        await self._nats.subscribe(
            "RESULTS.*",
            queue=f"workflow-workers-results",
            handler=self._handle_task_result,
            durable=f"workflow-worker-results-{self._worker_id}",
        )

        # Subscribe to control events
        await self._nats.subscribe(
            "WORKFLOWS.execution.cancelled",
            queue=f"workflow-workers",
            handler=self._handle_cancellation,
            durable=f"workflow-worker-cancel-{self._worker_id}",
        )

        logger.info("Workflow worker started", worker_id=self._worker_id)

        # Keep running
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the workflow worker gracefully."""
        logger.info("Stopping workflow worker", worker_id=self._worker_id)
        self._running = False

        # Cancel active executions
        for execution_id, task in self._active_executions.items():
            task.cancel()
            logger.info("Cancelled execution", execution_id=str(execution_id))

        # Wait for cancellations
        if self._active_executions:
            await asyncio.gather(
                *self._active_executions.values(),
                return_exceptions=True,
            )

        # Close connections
        if self._nats:
            await self._nats.close()
        if self._redis:
            await self._redis.close()

        logger.info("Workflow worker stopped", worker_id=self._worker_id)

    async def _handle_execution_start(self, data: dict[str, Any]) -> None:
        """Handle workflow execution start event."""
        execution_id = UUID(data["execution_id"])
        workflow_id = UUID(data["workflow_id"])

        logger.info(
            "Starting workflow execution",
            execution_id=str(execution_id),
            workflow_id=str(workflow_id),
        )

        # Load workflow definition (in production, this would come from database)
        # For now, create a mock definition
        definition = await self._load_workflow_definition(workflow_id)
        if not definition:
            logger.error("Workflow definition not found", workflow_id=str(workflow_id))
            return

        # Create execution
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_definition_id=workflow_id,
            input_data=data.get("input_data", {}),
        )

        # Run execution in background
        task = asyncio.create_task(self._run_execution(definition, execution))
        self._active_executions[execution_id] = task

    async def _run_execution(
        self,
        definition: WorkflowDefinition,
        execution: WorkflowExecution,
    ) -> None:
        """Run a workflow execution."""
        try:
            result = await self._workflow_engine.execute(definition, execution)

            logger.info(
                "Workflow execution completed",
                execution_id=str(execution.execution_id),
                status=result.status.value,
            )

        except asyncio.CancelledError:
            logger.info(
                "Workflow execution cancelled",
                execution_id=str(execution.execution_id),
            )
        except Exception as e:
            logger.exception(
                "Workflow execution failed",
                execution_id=str(execution.execution_id),
                error=str(e),
            )
        finally:
            self._active_executions.pop(execution.execution_id, None)

    async def _handle_task_result(self, data: dict[str, Any]) -> None:
        """Handle task result event."""
        await self._task_executor.handle_result(data)

    async def _handle_cancellation(self, data: dict[str, Any]) -> None:
        """Handle workflow cancellation event."""
        execution_id = UUID(data["execution_id"])
        task = self._active_executions.get(execution_id)

        if task:
            task.cancel()
            logger.info("Cancelling execution", execution_id=str(execution_id))

    async def _load_workflow_definition(self, workflow_id: UUID) -> WorkflowDefinition | None:
        """Load workflow definition from storage."""
        # In production, this would load from database
        # For now, return None (workflow should be passed in event data)
        return None

    async def _publish_event(self, event: Any) -> None:
        """Publish an event to the message broker."""
        if self._nats:
            await self._nats.publish(
                f"WORKFLOWS.events.{event.event_type.value}",
                event.model_dump(mode="json"),
            )
