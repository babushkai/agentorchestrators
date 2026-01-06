"""Agent management endpoints."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from agent_orchestrator.api.dependencies import NATSDep, RedisDep

router = APIRouter()


class LLMConfigRequest(BaseModel):
    """LLM model configuration."""

    provider: str = Field(default="anthropic", description="LLM provider")
    model_id: str = Field(default="claude-sonnet-4-20250514", description="Model ID")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)


class CreateAgentRequest(BaseModel):
    """Request to register a new agent."""

    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=1)
    backstory: str | None = None
    llm_config: LLMConfigRequest = Field(default_factory=LLMConfigRequest)
    tools: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    max_iterations: int = Field(default=25, ge=1, le=100)
    timeout_seconds: int = Field(default=300, gt=0, le=3600)


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


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    request: CreateAgentRequest,
    nats: NATSDep,
    redis: RedisDep,
) -> AgentResponse:
    """
    Register a new agent.

    Creates an agent definition that can be instantiated to handle tasks.
    """
    agent_id = uuid4()
    now = datetime.now(timezone.utc)

    agent_data = {
        "agent_id": str(agent_id),
        "name": request.name,
        "role": request.role,
        "goal": request.goal,
        "backstory": request.backstory,
        "llm_config": request.llm_config.model_dump(),
        "tools": request.tools,
        "capabilities": request.capabilities,
        "max_iterations": request.max_iterations,
        "timeout_seconds": request.timeout_seconds,
        "status": "idle",
        "created_at": now.isoformat(),
        "last_heartbeat": None,
        "current_task_id": None,
    }

    # Store agent in Redis
    await redis.set(f"agent:{agent_id}", agent_data, ttl=86400 * 30)  # 30 days TTL

    # Add to agents list index
    await redis.client.lpush("agents:list", str(agent_id))

    # Publish agent registered event to NATS
    await nats.publish("AGENTS.registered", agent_data)

    return AgentResponse(
        agent_id=agent_id,
        name=request.name,
        role=request.role,
        status="idle",
        capabilities=request.capabilities,
        created_at=now,
    )


@router.get("", response_model=AgentListResponse)
async def list_agents(
    redis: RedisDep,
    status: str | None = Query(None, description="Filter by status"),
    capability: str | None = Query(None, description="Filter by capability"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> AgentListResponse:
    """
    List registered agents with optional filtering.

    Returns a paginated list of agents.
    """
    # Get agent IDs from list
    start = (page - 1) * page_size
    end = start + page_size - 1
    agent_ids = await redis.client.lrange("agents:list", start, end)
    total = await redis.client.llen("agents:list")

    items = []
    for agent_id in agent_ids:
        agent_id_str = agent_id.decode() if isinstance(agent_id, bytes) else agent_id
        agent_data = await redis.get(f"agent:{agent_id_str}")
        if agent_data:
            # Filter by status if specified
            if status and agent_data.get("status") != status:
                continue
            # Filter by capability if specified
            if capability and capability not in agent_data.get("capabilities", []):
                continue
            items.append(
                AgentResponse(
                    agent_id=UUID(agent_data["agent_id"]),
                    name=agent_data["name"],
                    role=agent_data["role"],
                    status=agent_data["status"],
                    capabilities=agent_data.get("capabilities", []),
                    created_at=datetime.fromisoformat(agent_data["created_at"]),
                    last_heartbeat=datetime.fromisoformat(agent_data["last_heartbeat"])
                    if agent_data.get("last_heartbeat")
                    else None,
                    current_task_id=UUID(agent_data["current_task_id"])
                    if agent_data.get("current_task_id")
                    else None,
                )
            )

    return AgentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    redis: RedisDep,
) -> AgentResponse:
    """
    Get agent details by ID.

    Returns the current state and configuration of an agent.
    """
    from agent_orchestrator.api.middleware.error_handler import NotFoundError

    agent_data = await redis.get(f"agent:{agent_id}")
    if not agent_data:
        raise NotFoundError("Agent", str(agent_id))

    return AgentResponse(
        agent_id=UUID(agent_data["agent_id"]),
        name=agent_data["name"],
        role=agent_data["role"],
        status=agent_data["status"],
        capabilities=agent_data.get("capabilities", []),
        created_at=datetime.fromisoformat(agent_data["created_at"]),
        last_heartbeat=datetime.fromisoformat(agent_data["last_heartbeat"])
        if agent_data.get("last_heartbeat")
        else None,
        current_task_id=UUID(agent_data["current_task_id"])
        if agent_data.get("current_task_id")
        else None,
    )


@router.get("/{agent_id}/metrics", response_model=AgentMetricsResponse)
async def get_agent_metrics(
    agent_id: UUID,
    redis: RedisDep,
) -> AgentMetricsResponse:
    """
    Get agent performance metrics.

    Returns statistics about the agent's task execution history.
    """
    from agent_orchestrator.api.middleware.error_handler import NotFoundError

    # TODO: Implement actual metrics retrieval
    raise NotFoundError("Agent", str(agent_id))


@router.post("/{agent_id}/start", response_model=AgentResponse)
async def start_agent(
    agent_id: UUID,
    nats: NATSDep,
    redis: RedisDep,
) -> AgentResponse:
    """
    Start an idle agent.

    The agent will begin accepting tasks.
    """
    from agent_orchestrator.api.middleware.error_handler import NotFoundError

    agent_data = await redis.get(f"agent:{agent_id}")
    if not agent_data:
        raise NotFoundError("Agent", str(agent_id))

    # Update agent status
    agent_data["status"] = "running"
    await redis.set(f"agent:{agent_id}", agent_data, ttl=86400 * 30)

    # Publish agent start command
    await nats.publish(
        "AGENTS.commands.start",
        {
            "agent_id": str(agent_id),
            "requested_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return AgentResponse(
        agent_id=UUID(agent_data["agent_id"]),
        name=agent_data["name"],
        role=agent_data["role"],
        status="running",
        capabilities=agent_data.get("capabilities", []),
        created_at=datetime.fromisoformat(agent_data["created_at"]),
        last_heartbeat=datetime.fromisoformat(agent_data["last_heartbeat"])
        if agent_data.get("last_heartbeat")
        else None,
        current_task_id=UUID(agent_data["current_task_id"])
        if agent_data.get("current_task_id")
        else None,
    )


@router.post("/{agent_id}/stop", response_model=AgentResponse)
async def stop_agent(
    agent_id: UUID,
    nats: NATSDep,
    redis: RedisDep,
    graceful: bool = Query(True, description="Wait for current task to complete"),
) -> AgentResponse:
    """
    Stop a running agent.

    If graceful is True, the agent will complete its current task before stopping.
    """
    from agent_orchestrator.api.middleware.error_handler import NotFoundError

    agent_data = await redis.get(f"agent:{agent_id}")
    if not agent_data:
        raise NotFoundError("Agent", str(agent_id))

    # Update agent status
    agent_data["status"] = "stopped"
    await redis.set(f"agent:{agent_id}", agent_data, ttl=86400 * 30)

    # Publish agent stop command
    await nats.publish(
        "AGENTS.commands.stop",
        {
            "agent_id": str(agent_id),
            "graceful": graceful,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return AgentResponse(
        agent_id=UUID(agent_data["agent_id"]),
        name=agent_data["name"],
        role=agent_data["role"],
        status="stopped",
        capabilities=agent_data.get("capabilities", []),
        created_at=datetime.fromisoformat(agent_data["created_at"]),
        last_heartbeat=datetime.fromisoformat(agent_data["last_heartbeat"])
        if agent_data.get("last_heartbeat")
        else None,
        current_task_id=UUID(agent_data["current_task_id"])
        if agent_data.get("current_task_id")
        else None,
    )


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    nats: NATSDep,
    redis: RedisDep,
) -> None:
    """
    Delete an agent.

    The agent must be stopped before deletion.
    """
    # Delete from Redis
    await redis.client.delete(f"agent:{agent_id}")
    await redis.client.lrem("agents:list", 0, str(agent_id))

    # Publish deletion event
    await nats.publish(
        "AGENTS.deleted",
        {
            "agent_id": str(agent_id),
            "deleted_at": datetime.now(timezone.utc).isoformat(),
        },
    )
