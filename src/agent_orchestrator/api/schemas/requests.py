"""API request schemas."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ModelConfigRequest(BaseModel):
    """LLM model configuration request."""

    provider: str = Field(default="anthropic", description="LLM provider")
    model_id: str = Field(default="claude-sonnet-4-20250514", description="Model ID")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)


class CreateTaskRequest(BaseModel):
    """Request to create a new task."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    input_data: dict[str, Any] = Field(default_factory=dict)
    required_capabilities: list[str] = Field(default_factory=list)
    priority: int = Field(default=1, ge=0, le=3)
    timeout_seconds: int = Field(default=300, gt=0, le=3600)
    webhook_url: str | None = None
    idempotency_key: str | None = None

    model_config = {"json_schema_extra": {
        "examples": [
            {
                "name": "Research Task",
                "description": "Research the latest developments in AI agents",
                "input_data": {"topic": "AI agents"},
                "required_capabilities": ["research"],
                "priority": 1,
            }
        ]
    }}


class CreateAgentRequest(BaseModel):
    """Request to register a new agent."""

    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=1)
    backstory: str | None = None
    llm_config: ModelConfigRequest = Field(default_factory=ModelConfigRequest)
    tools: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    max_iterations: int = Field(default=25, ge=1, le=100)
    timeout_seconds: int = Field(default=300, gt=0, le=3600)


class WorkflowStepRequest(BaseModel):
    """A step in a workflow definition."""

    step_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    step_type: str = Field(default="agent_task")
    agent_id: UUID | None = None
    task_template: dict[str, Any] | None = None
    condition: str | None = None
    children: list["WorkflowStepRequest"] = Field(default_factory=list)
    timeout_seconds: int = Field(default=300, gt=0)
    depends_on: list[str] = Field(default_factory=list)


class CreateWorkflowRequest(BaseModel):
    """Request to create a workflow definition."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")
    steps: list[WorkflowStepRequest]
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None


class StartWorkflowRequest(BaseModel):
    """Request to start a workflow execution."""

    input_data: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=1, ge=0, le=3)
    callback_url: str | None = None
