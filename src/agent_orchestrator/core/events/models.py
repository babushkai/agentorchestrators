"""Domain event models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of domain events."""

    # Task events
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    TASK_TIMEOUT = "task.timeout"

    # Agent events
    AGENT_REGISTERED = "agent.registered"
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_HEARTBEAT = "agent.heartbeat"
    AGENT_LLM_CALL = "agent.llm_call"
    AGENT_TOOL_CALL = "agent.tool_call"
    AGENT_THINKING = "agent.thinking"
    AGENT_OUTPUT = "agent.output"
    AGENT_ERROR = "agent.error"

    # Workflow events
    WORKFLOW_CREATED = "workflow.created"
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_STEP_STARTED = "workflow.step.started"
    WORKFLOW_STEP_COMPLETED = "workflow.step.completed"
    WORKFLOW_STEP_FAILED = "workflow.step.failed"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_PAUSED = "workflow.paused"
    WORKFLOW_RESUMED = "workflow.resumed"
    WORKFLOW_CANCELLED = "workflow.cancelled"
    WORKFLOW_COMPENSATING = "workflow.compensating"
    WORKFLOW_COMPENSATED = "workflow.compensated"

    # System events
    SYSTEM_SCALE_UP = "system.scale_up"
    SYSTEM_SCALE_DOWN = "system.scale_down"
    SYSTEM_CIRCUIT_OPEN = "system.circuit_open"
    SYSTEM_CIRCUIT_CLOSE = "system.circuit_close"


class DomainEvent(BaseModel):
    """Base class for all domain events."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    aggregate_id: UUID
    aggregate_type: str
    tenant_id: str = "default"
    version: int = 1
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def with_causation(self, event: "DomainEvent") -> "DomainEvent":
        """Create a new event with causation chain."""
        self.causation_id = event.event_id
        self.correlation_id = event.correlation_id or event.event_id
        return self


class TaskEvent(DomainEvent):
    """Event related to task lifecycle."""

    aggregate_type: str = "Task"

    @classmethod
    def created(
        cls,
        task_id: UUID,
        name: str,
        description: str,
        input_data: dict[str, Any],
        tenant_id: str = "default",
    ) -> "TaskEvent":
        return cls(
            event_type=EventType.TASK_CREATED,
            aggregate_id=task_id,
            tenant_id=tenant_id,
            payload={
                "name": name,
                "description": description,
                "input_data": input_data,
            },
        )

    @classmethod
    def assigned(
        cls,
        task_id: UUID,
        agent_id: UUID,
        tenant_id: str = "default",
    ) -> "TaskEvent":
        return cls(
            event_type=EventType.TASK_ASSIGNED,
            aggregate_id=task_id,
            tenant_id=tenant_id,
            payload={"agent_id": str(agent_id)},
        )

    @classmethod
    def completed(
        cls,
        task_id: UUID,
        result: Any,
        tenant_id: str = "default",
    ) -> "TaskEvent":
        return cls(
            event_type=EventType.TASK_COMPLETED,
            aggregate_id=task_id,
            tenant_id=tenant_id,
            payload={"result": result},
        )

    @classmethod
    def failed(
        cls,
        task_id: UUID,
        error: str,
        tenant_id: str = "default",
    ) -> "TaskEvent":
        return cls(
            event_type=EventType.TASK_FAILED,
            aggregate_id=task_id,
            tenant_id=tenant_id,
            payload={"error": error},
        )


class AgentEvent(DomainEvent):
    """Event related to agent lifecycle and execution."""

    aggregate_type: str = "Agent"

    @classmethod
    def llm_call(
        cls,
        agent_id: UUID,
        task_id: UUID,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        tenant_id: str = "default",
    ) -> "AgentEvent":
        return cls(
            event_type=EventType.AGENT_LLM_CALL,
            aggregate_id=agent_id,
            tenant_id=tenant_id,
            payload={
                "task_id": str(task_id),
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms,
            },
        )

    @classmethod
    def tool_call(
        cls,
        agent_id: UUID,
        task_id: UUID,
        tool_name: str,
        success: bool,
        execution_time_ms: float,
        tenant_id: str = "default",
    ) -> "AgentEvent":
        return cls(
            event_type=EventType.AGENT_TOOL_CALL,
            aggregate_id=agent_id,
            tenant_id=tenant_id,
            payload={
                "task_id": str(task_id),
                "tool_name": tool_name,
                "success": success,
                "execution_time_ms": execution_time_ms,
            },
        )


class WorkflowEvent(DomainEvent):
    """Event related to workflow execution."""

    aggregate_type: str = "Workflow"

    @classmethod
    def started(
        cls,
        workflow_id: UUID,
        execution_id: UUID,
        input_data: dict[str, Any],
        tenant_id: str = "default",
    ) -> "WorkflowEvent":
        return cls(
            event_type=EventType.WORKFLOW_STARTED,
            aggregate_id=execution_id,
            tenant_id=tenant_id,
            payload={
                "workflow_id": str(workflow_id),
                "input_data": input_data,
            },
        )

    @classmethod
    def step_completed(
        cls,
        execution_id: UUID,
        step_id: str,
        result: Any,
        tenant_id: str = "default",
    ) -> "WorkflowEvent":
        return cls(
            event_type=EventType.WORKFLOW_STEP_COMPLETED,
            aggregate_id=execution_id,
            tenant_id=tenant_id,
            payload={
                "step_id": step_id,
                "result": result,
            },
        )

    @classmethod
    def completed(
        cls,
        execution_id: UUID,
        result: Any,
        tenant_id: str = "default",
    ) -> "WorkflowEvent":
        return cls(
            event_type=EventType.WORKFLOW_COMPLETED,
            aggregate_id=execution_id,
            tenant_id=tenant_id,
            payload={"result": result},
        )

    @classmethod
    def failed(
        cls,
        execution_id: UUID,
        step_id: str | None,
        error: str,
        tenant_id: str = "default",
    ) -> "WorkflowEvent":
        return cls(
            event_type=EventType.WORKFLOW_FAILED,
            aggregate_id=execution_id,
            tenant_id=tenant_id,
            payload={
                "step_id": step_id,
                "error": error,
            },
        )
