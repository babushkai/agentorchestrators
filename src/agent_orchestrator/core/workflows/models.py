"""Workflow and task models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TaskPriority(int, Enum):
    """Task priority levels."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskStatus(str, Enum):
    """Task lifecycle status."""

    PENDING = "pending"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class Task(BaseModel):
    """A unit of work for an agent."""

    task_id: UUID = Field(default_factory=uuid4)
    tenant_id: str = "default"
    name: str
    description: str
    input_data: dict[str, Any] = Field(default_factory=dict)

    # Routing
    required_capabilities: set[str] = Field(default_factory=set)
    priority: TaskPriority = TaskPriority.NORMAL

    # Status
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_id: UUID | None = None

    # Workflow context
    parent_workflow_id: UUID | None = None
    parent_step_id: str | None = None

    # Execution settings
    timeout_seconds: int = Field(default=300, gt=0)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)

    # Lifecycle timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Results
    result: dict[str, Any] | None = None
    error: str | None = None

    def start(self, agent_id: UUID) -> None:
        """Mark task as started."""
        self.status = TaskStatus.RUNNING
        self.assigned_agent_id = agent_id
        self.started_at = datetime.now(timezone.utc)

    def complete(self, result: dict[str, Any]) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now(timezone.utc)

    def fail(self, error: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now(timezone.utc)

    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retry_count < self.max_retries


class WorkflowStepType(str, Enum):
    """Types of workflow steps."""

    AGENT_TASK = "agent_task"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    WAIT = "wait"
    HUMAN_APPROVAL = "human_approval"
    SUBPROCESS = "subprocess"


class WorkflowStep(BaseModel):
    """A step in a workflow."""

    step_id: str
    name: str
    step_type: WorkflowStepType = WorkflowStepType.AGENT_TASK

    # For AGENT_TASK
    agent_id: UUID | None = None
    task_template: dict[str, Any] | None = None

    # For CONDITIONAL
    condition: str | None = None  # Expression to evaluate

    # For child steps (PARALLEL, LOOP)
    children: list["WorkflowStep"] = Field(default_factory=list)

    # For WAIT
    wait_seconds: int | None = None

    # Saga compensation
    compensation: dict[str, Any] | None = None

    # Execution settings
    timeout_seconds: int = Field(default=300, gt=0)
    retry_policy: dict[str, Any] | None = None

    # Dependencies
    depends_on: list[str] = Field(default_factory=list)


class WorkflowDefinition(BaseModel):
    """Definition of a multi-step workflow."""

    workflow_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    version: str = "1.0.0"

    # Steps
    steps: list[WorkflowStep] = Field(default_factory=list)

    # Input/output schemas
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None

    # Metadata
    tenant_id: str = "default"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_step(self, step_id: str) -> WorkflowStep | None:
        """Find a step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
            # Search in children
            for child in step.children:
                if child.step_id == step_id:
                    return child
        return None


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    CANCELLED = "cancelled"


class WorkflowExecution(BaseModel):
    """Runtime execution of a workflow."""

    execution_id: UUID = Field(default_factory=uuid4)
    workflow_definition_id: UUID
    tenant_id: str = "default"

    # Status
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step_id: str | None = None

    # Progress tracking
    completed_steps: list[str] = Field(default_factory=list)
    step_results: dict[str, Any] = Field(default_factory=dict)
    failed_step_id: str | None = None

    # Input/output
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] | None = None

    # Checkpointing
    checkpoint_data: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Error info
    error: str | None = None

    @property
    def progress_percentage(self) -> float:
        """Calculate progress as a percentage."""
        if not self.checkpoint_data.get("total_steps"):
            return 0.0
        total = self.checkpoint_data["total_steps"]
        completed = len(self.completed_steps)
        return (completed / total) * 100

    def start(self) -> None:
        """Start the workflow execution."""
        self.status = WorkflowStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def complete_step(self, step_id: str, result: Any) -> None:
        """Mark a step as completed."""
        self.completed_steps.append(step_id)
        self.step_results[step_id] = result

    def fail(self, step_id: str, error: str) -> None:
        """Mark the workflow as failed."""
        self.status = WorkflowStatus.FAILED
        self.failed_step_id = step_id
        self.error = error
        self.completed_at = datetime.now(timezone.utc)

    def complete(self, output: dict[str, Any]) -> None:
        """Mark the workflow as completed."""
        self.status = WorkflowStatus.COMPLETED
        self.output_data = output
        self.completed_at = datetime.now(timezone.utc)
