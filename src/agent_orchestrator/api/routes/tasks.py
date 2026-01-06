"""Task management endpoints."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from agent_orchestrator.api.dependencies import NATSDep, RedisDep

router = APIRouter()


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
    result: Any = None
    error: str | None = None


class TaskListResponse(BaseModel):
    """Response for listing tasks."""

    items: list[TaskResponse]
    total: int
    page: int
    page_size: int


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    request: CreateTaskRequest,
    nats: NATSDep,
    redis: RedisDep,
) -> TaskResponse:
    """
    Create a new task.

    The task will be queued and assigned to an available agent
    based on required capabilities and priority.
    """
    task_id = uuid4()
    now = datetime.now(timezone.utc)

    task_data = {
        "task_id": str(task_id),
        "name": request.name,
        "description": request.description,
        "input_data": request.input_data,
        "required_capabilities": request.required_capabilities,
        "priority": request.priority,
        "timeout_seconds": request.timeout_seconds,
        "webhook_url": request.webhook_url,
        "status": "pending",
        "created_at": now.isoformat(),
        "started_at": None,
        "completed_at": None,
        "assigned_agent_id": None,
        "result": None,
        "error": None,
    }

    # Store task in Redis
    await redis.set(f"task:{task_id}", task_data, ttl=86400 * 7)  # 7 days TTL

    # Add to task list index
    await redis.client.lpush("tasks:list", str(task_id))

    # Publish task created event to NATS
    await nats.publish("TASKS.created", task_data)

    return TaskResponse(
        task_id=task_id,
        name=request.name,
        status="pending",
        priority=request.priority,
        created_at=now,
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    redis: RedisDep,
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> TaskListResponse:
    """
    List tasks with optional filtering.

    Returns a paginated list of tasks.
    """
    # Get task IDs from list
    start = (page - 1) * page_size
    end = start + page_size - 1
    task_ids = await redis.client.lrange("tasks:list", start, end)
    total = await redis.client.llen("tasks:list")

    items = []
    for task_id in task_ids:
        task_id_str = task_id.decode() if isinstance(task_id, bytes) else task_id
        task_data = await redis.get(f"task:{task_id_str}")
        if task_data:
            # Filter by status if specified
            if status and task_data.get("status") != status:
                continue
            items.append(
                TaskResponse(
                    task_id=UUID(task_data["task_id"]),
                    name=task_data["name"],
                    status=task_data["status"],
                    priority=task_data["priority"],
                    created_at=datetime.fromisoformat(task_data["created_at"]),
                    started_at=datetime.fromisoformat(task_data["started_at"])
                    if task_data.get("started_at")
                    else None,
                    completed_at=datetime.fromisoformat(task_data["completed_at"])
                    if task_data.get("completed_at")
                    else None,
                    assigned_agent_id=UUID(task_data["assigned_agent_id"])
                    if task_data.get("assigned_agent_id")
                    else None,
                    result=task_data.get("result"),
                    error=task_data.get("error"),
                )
            )

    return TaskListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    redis: RedisDep,
) -> TaskResponse:
    """
    Get task details by ID.

    Returns the current state and result of a task.
    """
    from agent_orchestrator.api.middleware.error_handler import NotFoundError

    task_data = await redis.get(f"task:{task_id}")
    if not task_data:
        raise NotFoundError("Task", str(task_id))

    return TaskResponse(
        task_id=UUID(task_data["task_id"]),
        name=task_data["name"],
        status=task_data["status"],
        priority=task_data["priority"],
        created_at=datetime.fromisoformat(task_data["created_at"]),
        started_at=datetime.fromisoformat(task_data["started_at"])
        if task_data.get("started_at")
        else None,
        completed_at=datetime.fromisoformat(task_data["completed_at"])
        if task_data.get("completed_at")
        else None,
        assigned_agent_id=UUID(task_data["assigned_agent_id"])
        if task_data.get("assigned_agent_id")
        else None,
        result=task_data.get("result"),
        error=task_data.get("error"),
    )


@router.delete("/{task_id}", status_code=204)
async def cancel_task(
    task_id: UUID,
    nats: NATSDep,
    redis: RedisDep,
) -> None:
    """
    Cancel a pending or running task.

    If the task is already completed, this operation has no effect.
    """
    # Update task status in Redis
    task_data = await redis.get(f"task:{task_id}")
    if task_data:
        task_data["status"] = "cancelled"
        task_data["completed_at"] = datetime.now(timezone.utc).isoformat()
        await redis.set(f"task:{task_id}", task_data, ttl=86400 * 7)

    # Publish task cancellation event
    await nats.publish(
        "TASKS.cancelled",
        {
            "task_id": str(task_id),
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
        },
    )
