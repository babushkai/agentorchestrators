"""Workflow management endpoints."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from agent_orchestrator.api.dependencies import NATSDep, RedisDep

router = APIRouter()


class WorkflowStepRequest(BaseModel):
    """A step in a workflow definition."""

    step_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    step_type: str = Field(default="agent_task")  # agent_task, parallel, conditional, wait
    agent_id: UUID | None = None
    task_template: dict[str, Any] | None = None
    condition: str | None = None
    children: list["WorkflowStepRequest"] = Field(default_factory=list)
    timeout_seconds: int = Field(default=300, gt=0)


class CreateWorkflowRequest(BaseModel):
    """Request to create a workflow definition."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")
    steps: list[WorkflowStepRequest]
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None


class WorkflowResponse(BaseModel):
    """Response for workflow definition operations."""

    workflow_id: UUID
    name: str
    description: str
    version: str
    step_count: int
    created_at: datetime
    updated_at: datetime


class StartWorkflowRequest(BaseModel):
    """Request to start a workflow execution."""

    input_data: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=1, ge=0, le=3)
    callback_url: str | None = None


class WorkflowExecutionResponse(BaseModel):
    """Response for workflow execution."""

    execution_id: UUID
    workflow_id: UUID
    status: str
    current_step: str | None = None
    progress_percentage: float
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


class WorkflowListResponse(BaseModel):
    """Response for listing workflows."""

    items: list[WorkflowResponse]
    total: int
    page: int
    page_size: int


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    request: CreateWorkflowRequest,
    nats: NATSDep,
    redis: RedisDep,
) -> WorkflowResponse:
    """
    Create a new workflow definition.

    Defines a multi-step workflow that orchestrates multiple agents.
    """
    workflow_id = uuid4()
    now = datetime.now(timezone.utc)

    workflow_data = {
        "workflow_id": str(workflow_id),
        "name": request.name,
        "description": request.description,
        "steps": [step.model_dump() for step in request.steps],
        "input_schema": request.input_schema,
        "output_schema": request.output_schema,
        "version": "1.0.0",
        "status": "active",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    # Store workflow in Redis
    await redis.set(f"workflow:{workflow_id}", workflow_data, ttl=86400 * 30)

    # Add to workflows list index
    await redis.client.lpush("workflows:list", str(workflow_id))

    # Publish workflow created event
    await nats.publish("WORKFLOWS.created", workflow_data)

    return WorkflowResponse(
        workflow_id=workflow_id,
        name=request.name,
        description=request.description,
        version="1.0.0",
        step_count=len(request.steps),
        created_at=now,
        updated_at=now,
    )


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    redis: RedisDep,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> WorkflowListResponse:
    """
    List all workflow definitions.

    Returns all available workflow definitions.
    """
    # Get workflow IDs from list
    start = (page - 1) * page_size
    end = start + page_size - 1
    workflow_ids = await redis.client.lrange("workflows:list", start, end)
    total = await redis.client.llen("workflows:list")

    items = []
    for workflow_id in workflow_ids:
        wf_id_str = workflow_id.decode() if isinstance(workflow_id, bytes) else workflow_id
        workflow_data = await redis.get(f"workflow:{wf_id_str}")
        if workflow_data:
            items.append(
                WorkflowResponse(
                    workflow_id=UUID(workflow_data["workflow_id"]),
                    name=workflow_data["name"],
                    description=workflow_data.get("description", ""),
                    version=workflow_data.get("version", "1.0.0"),
                    step_count=len(workflow_data.get("steps", [])),
                    created_at=datetime.fromisoformat(workflow_data["created_at"]),
                    updated_at=datetime.fromisoformat(workflow_data["updated_at"]),
                )
            )

    return WorkflowListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    redis: RedisDep,
) -> WorkflowResponse:
    """
    Get workflow definition by ID.
    """
    from agent_orchestrator.api.middleware.error_handler import NotFoundError

    workflow_data = await redis.get(f"workflow:{workflow_id}")
    if not workflow_data:
        raise NotFoundError("Workflow", str(workflow_id))

    return WorkflowResponse(
        workflow_id=UUID(workflow_data["workflow_id"]),
        name=workflow_data["name"],
        description=workflow_data.get("description", ""),
        version=workflow_data.get("version", "1.0.0"),
        step_count=len(workflow_data.get("steps", [])),
        created_at=datetime.fromisoformat(workflow_data["created_at"]),
        updated_at=datetime.fromisoformat(workflow_data["updated_at"]),
    )


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse, status_code=201)
async def start_workflow_execution(
    workflow_id: UUID,
    request: StartWorkflowRequest,
    nats: NATSDep,
    redis: RedisDep,
) -> WorkflowExecutionResponse:
    """
    Start a new execution of a workflow.

    Creates a new workflow execution instance and begins processing.
    """
    execution_id = uuid4()
    now = datetime.now(timezone.utc)

    execution_data = {
        "execution_id": str(execution_id),
        "workflow_id": str(workflow_id),
        "status": "running",
        "input_data": request.input_data,
        "priority": request.priority,
        "callback_url": request.callback_url,
        "current_step": None,
        "completed_steps": [],
        "step_results": {},
        "progress_percentage": 0.0,
        "started_at": now.isoformat(),
        "completed_at": None,
        "result": None,
        "error": None,
    }

    # Store execution in Redis
    await redis.set(f"workflow_execution:{execution_id}", execution_data, ttl=86400 * 7)

    # Add to workflow executions list
    await redis.client.lpush(f"workflow:{workflow_id}:executions", str(execution_id))

    # Publish workflow execution started event
    await nats.publish("WORKFLOWS.execution.started", execution_data)

    return WorkflowExecutionResponse(
        execution_id=execution_id,
        workflow_id=workflow_id,
        status="running",
        progress_percentage=0.0,
        started_at=now,
    )


@router.get("/{workflow_id}/executions", response_model=WorkflowExecutionListResponse)
async def list_workflow_executions(
    workflow_id: UUID,
    redis: RedisDep,
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> WorkflowExecutionListResponse:
    """
    List executions of a workflow.

    Returns a paginated list of execution instances.
    """
    # Get execution IDs from list
    start = (page - 1) * page_size
    end = start + page_size - 1
    execution_ids = await redis.client.lrange(f"workflow:{workflow_id}:executions", start, end)
    total = await redis.client.llen(f"workflow:{workflow_id}:executions")

    items = []
    for exec_id in execution_ids:
        exec_id_str = exec_id.decode() if isinstance(exec_id, bytes) else exec_id
        exec_data = await redis.get(f"workflow_execution:{exec_id_str}")
        if exec_data:
            if status and exec_data.get("status") != status:
                continue
            items.append(
                WorkflowExecutionResponse(
                    execution_id=UUID(exec_data["execution_id"]),
                    workflow_id=UUID(exec_data["workflow_id"]),
                    status=exec_data["status"],
                    current_step=exec_data.get("current_step"),
                    progress_percentage=exec_data.get("progress_percentage", 0.0),
                    started_at=datetime.fromisoformat(exec_data["started_at"])
                    if exec_data.get("started_at")
                    else None,
                    completed_at=datetime.fromisoformat(exec_data["completed_at"])
                    if exec_data.get("completed_at")
                    else None,
                    result=exec_data.get("result"),
                    error=exec_data.get("error"),
                )
            )

    return WorkflowExecutionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/executions/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_workflow_execution(
    execution_id: UUID,
    redis: RedisDep,
) -> WorkflowExecutionResponse:
    """
    Get workflow execution details.

    Returns the current state and progress of a workflow execution.
    """
    from agent_orchestrator.api.middleware.error_handler import NotFoundError

    exec_data = await redis.get(f"workflow_execution:{execution_id}")
    if not exec_data:
        raise NotFoundError("WorkflowExecution", str(execution_id))

    return WorkflowExecutionResponse(
        execution_id=UUID(exec_data["execution_id"]),
        workflow_id=UUID(exec_data["workflow_id"]),
        status=exec_data["status"],
        current_step=exec_data.get("current_step"),
        progress_percentage=exec_data.get("progress_percentage", 0.0),
        started_at=datetime.fromisoformat(exec_data["started_at"])
        if exec_data.get("started_at")
        else None,
        completed_at=datetime.fromisoformat(exec_data["completed_at"])
        if exec_data.get("completed_at")
        else None,
        result=exec_data.get("result"),
        error=exec_data.get("error"),
    )


@router.post("/executions/{execution_id}/cancel", status_code=204)
async def cancel_workflow_execution(
    execution_id: UUID,
    nats: NATSDep,
) -> None:
    """
    Cancel a running workflow execution.

    Triggers compensation logic for completed steps (saga rollback).
    """
    await nats.publish(
        "WORKFLOWS.execution.cancelled",
        {
            "execution_id": str(execution_id),
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
        },
    )


@router.post("/executions/{execution_id}/pause", status_code=204)
async def pause_workflow_execution(
    execution_id: UUID,
    nats: NATSDep,
) -> None:
    """
    Pause a running workflow execution.

    The execution can be resumed later.
    """
    await nats.publish(
        "WORKFLOWS.execution.paused",
        {
            "execution_id": str(execution_id),
            "paused_at": datetime.now(timezone.utc).isoformat(),
        },
    )


@router.post("/executions/{execution_id}/resume", status_code=204)
async def resume_workflow_execution(
    execution_id: UUID,
    nats: NATSDep,
) -> None:
    """
    Resume a paused workflow execution.
    """
    await nats.publish(
        "WORKFLOWS.execution.resumed",
        {
            "execution_id": str(execution_id),
            "resumed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
