"""API response schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TaskResponse(BaseModel):
    """Response for task operations."""

    task_id: UUID
    name: str
    status: str
    priority: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assigned_agent_id: UUID | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class TaskListResponse(BaseModel):
    """Response for listing tasks."""

    items: list[TaskResponse]
    total: int
    page: int
    page_size: int


class AgentResponse(BaseModel):
    """Response for agent operations."""

    agent_id: UUID
    name: str
    role: str
    status: str
    capabilities: list[str]
    created_at: datetime
    last_heartbeat: datetime | None = None
    current_task_id: UUID | None = None


class AgentListResponse(BaseModel):
    """Response for listing agents."""

    items: list[AgentResponse]
    total: int
    page: int
    page_size: int


class AgentMetricsResponse(BaseModel):
    """Agent metrics and statistics."""

    agent_id: UUID
    tasks_completed: int
    tasks_failed: int
    avg_task_duration_ms: float
    total_tokens_used: int
    uptime_seconds: float


class WorkflowResponse(BaseModel):
    """Response for workflow definition operations."""

    workflow_id: UUID
    name: str
    description: str
    version: str
    step_count: int
    created_at: datetime
    updated_at: datetime


class WorkflowExecutionResponse(BaseModel):
    """Response for workflow execution."""

    execution_id: UUID
    workflow_id: UUID
    status: str
    current_step: str | None = None
    progress_percentage: float = 0.0
    completed_steps: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class WorkflowExecutionListResponse(BaseModel):
    """Response for listing workflow executions."""

    items: list[WorkflowExecutionResponse]
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: "ErrorDetail"


class ErrorDetail(BaseModel):
    """Error detail."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: datetime
    version: str
    environment: str
    checks: dict[str, Any] = Field(default_factory=dict)


class MetricsResponse(BaseModel):
    """System metrics response."""

    queue_depth: int
    pending_tasks: int
    total_agents: int
    active_agents: int
    idle_agents: int
    error_agents: int
