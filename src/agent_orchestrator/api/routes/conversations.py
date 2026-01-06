"""Conversation session API routes."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent_orchestrator.api.dependencies import NATSDep, RedisDep
from agent_orchestrator.core.conversation.session import (
    ConversationMessage,
    ConversationSession,
    SessionManager,
    SessionStatus,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


# Request/Response Models
class CreateSessionRequest(BaseModel):
    """Request to create a conversation session."""

    agent_id: UUID
    title: str | None = None
    system_prompt: str | None = None
    max_history_messages: int = Field(default=50, ge=1, le=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    """Response with session details."""

    session_id: UUID
    agent_id: UUID
    tenant_id: str
    status: str
    title: str | None
    created_at: datetime
    last_activity_at: datetime
    message_count: int


class SendMessageRequest(BaseModel):
    """Request to send a message in a session."""

    content: str
    attachments: list[UUID] = Field(default_factory=list)
    stream: bool = False


class MessageResponse(BaseModel):
    """Response with a message."""

    message_id: UUID
    role: str
    content: str
    timestamp: datetime
    tool_calls: list[dict[str, Any]] | None = None


class ConversationHistoryResponse(BaseModel):
    """Response with conversation history."""

    session_id: UUID
    messages: list[MessageResponse]
    total_count: int
    has_more: bool


# Helper functions
def _get_session_manager(redis: RedisDep) -> SessionManager:
    """Create session manager from Redis dependency."""
    return SessionManager(redis)


# Routes
@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    redis: RedisDep,
) -> SessionResponse:
    """Create a new conversation session."""
    manager = _get_session_manager(redis)

    session = await manager.create_session(
        agent_id=request.agent_id,
        title=request.title,
        system_prompt_override=request.system_prompt,
        max_history_messages=request.max_history_messages,
        metadata=request.metadata,
    )

    return SessionResponse(
        session_id=session.id,
        agent_id=session.agent_id,
        tenant_id=session.tenant_id,
        status=session.status.value,
        title=session.title,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
        message_count=session.message_count,
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    redis: RedisDep,
) -> SessionResponse:
    """Get session details."""
    manager = _get_session_manager(redis)
    session = await manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        session_id=session.id,
        agent_id=session.agent_id,
        tenant_id=session.tenant_id,
        status=session.status.value,
        title=session.title,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
        message_count=session.message_count,
    )


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    redis: RedisDep,
    agent_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[SessionResponse]:
    """List conversation sessions."""
    manager = _get_session_manager(redis)

    # Convert status string to enum
    status_enum = None
    if status:
        try:
            status_enum = SessionStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: {[s.value for s in SessionStatus]}",
            )

    sessions = await manager.list_sessions(
        agent_id=agent_id,
        status=status_enum,
        limit=limit,
    )

    return [
        SessionResponse(
            session_id=s.id,
            agent_id=s.agent_id,
            tenant_id=s.tenant_id,
            status=s.status.value,
            title=s.title,
            created_at=s.created_at,
            last_activity_at=s.last_activity_at,
            message_count=s.message_count,
        )
        for s in sessions
    ]


@router.post("/sessions/{session_id}/messages", response_model=None)
async def send_message(
    session_id: UUID,
    request: SendMessageRequest,
    redis: RedisDep,
    nats: NATSDep,
) -> MessageResponse | StreamingResponse:
    """Send a message in a conversation session."""
    manager = _get_session_manager(redis)
    session = await manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"Session is {session.status.value}. Only active sessions accept messages.",
        )

    # Store user message
    user_message = await manager.add_message(
        session_id=session_id,
        role="user",
        content=request.content,
        metadata={"attachments": [str(a) for a in request.attachments]} if request.attachments else {},
    )

    # Create task for agent processing
    task_id = uuid4()
    now = datetime.now(timezone.utc)
    task_data = {
        "task_id": str(task_id),
        "session_id": str(session_id),
        "agent_id": str(session.agent_id),
        "name": f"Conversation message in {session_id}",
        "description": request.content,
        "attachments": [str(a) for a in request.attachments],
        "is_conversation": True,
        "tenant_id": session.tenant_id,
        "status": "pending",
        "created_at": now.isoformat(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }

    # Store task in Redis before publishing (required for result_handler to update it)
    await redis.set(f"task:{task_id}", task_data, ttl=86400)  # 1 day TTL

    # Publish task
    await nats.publish("TASKS.created", task_data)

    # Update session activity
    await manager.update_activity(session_id)

    if request.stream:
        return StreamingResponse(
            _stream_response(session_id, task_id, nats, manager),
            media_type="text/event-stream",
        )

    # Wait for response (synchronous)
    response_content = await _wait_for_response(task_id, redis, timeout=300)

    # Store assistant message
    assistant_message = await manager.add_message(
        session_id=session_id,
        role="assistant",
        content=response_content,
    )

    return MessageResponse(
        message_id=assistant_message.id,
        role="assistant",
        content=response_content,
        timestamp=assistant_message.created_at,
    )


async def _wait_for_response(
    task_id: UUID,
    redis: RedisDep,
    timeout: int = 300,
) -> str:
    """Wait for task response."""
    start = asyncio.get_event_loop().time()

    while asyncio.get_event_loop().time() - start < timeout:
        # Check task status
        task_data = await redis.get(f"task:{task_id}")
        if task_data:
            status = task_data.get("status")
            if status == "completed":
                return task_data.get("result", "")
            elif status == "failed":
                error = task_data.get("error", "Unknown error")
                raise HTTPException(status_code=500, detail=f"Task failed: {error}")

        await asyncio.sleep(0.5)

    raise HTTPException(status_code=504, detail="Request timed out")


async def _stream_response(
    session_id: UUID,
    task_id: UUID,
    nats: NATSDep,
    manager: SessionManager,
):
    """Stream SSE events for conversation response."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    full_content = ""

    async def handle_event(data: dict[str, Any]) -> None:
        if data.get("task_id") == str(task_id):
            await queue.put(data)

    # Subscribe to task events
    subscription = await nats.subscribe(
        f"TASKS.{task_id}.*",
        handler=handle_event,
    )

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=60)
                event_type = event.get("type", "unknown")

                if event_type == "chunk":
                    content = event.get("content", "")
                    full_content += content
                    yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"

                elif event_type == "tool_call":
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': event.get('tool_name')})}\n\n"

                elif event_type == "completed":
                    result = event.get("result", full_content)
                    yield f"data: {json.dumps({'type': 'completed', 'content': result})}\n\n"

                    # Store assistant message
                    await manager.add_message(
                        session_id=session_id,
                        role="assistant",
                        content=result,
                    )
                    break

                elif event_type == "failed":
                    error = event.get("error", "Unknown error")
                    yield f"data: {json.dumps({'type': 'error', 'error': error})}\n\n"
                    break

            except asyncio.TimeoutError:
                # Send heartbeat
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    finally:
        # Cleanup subscription
        if subscription:
            await subscription.unsubscribe()


@router.get("/sessions/{session_id}/history", response_model=ConversationHistoryResponse)
async def get_history(
    session_id: UUID,
    redis: RedisDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ConversationHistoryResponse:
    """Get conversation history for a session."""
    manager = _get_session_manager(redis)
    session = await manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = await manager.get_messages(session_id, limit=limit, offset=offset)

    return ConversationHistoryResponse(
        session_id=session_id,
        messages=[
            MessageResponse(
                message_id=m.id,
                role=m.role,
                content=m.content,
                timestamp=m.created_at,
                tool_calls=m.tool_calls,
            )
            for m in messages
        ],
        total_count=session.message_count,
        has_more=offset + limit < session.message_count,
    )


@router.delete("/sessions/{session_id}/messages")
async def clear_messages(
    session_id: UUID,
    redis: RedisDep,
) -> dict[str, Any]:
    """Clear all messages in a session."""
    manager = _get_session_manager(redis)
    session = await manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    count = await manager.clear_messages(session_id)

    return {"cleared": count, "session_id": str(session_id)}


@router.post("/sessions/{session_id}/close")
async def close_session(
    session_id: UUID,
    redis: RedisDep,
) -> SessionResponse:
    """Close a conversation session."""
    manager = _get_session_manager(redis)

    success = await manager.close_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    session = await manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        session_id=session.id,
        agent_id=session.agent_id,
        tenant_id=session.tenant_id,
        status=session.status.value,
        title=session.title,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
        message_count=session.message_count,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: UUID,
    redis: RedisDep,
) -> dict[str, Any]:
    """Delete a conversation session and all its data."""
    manager = _get_session_manager(redis)

    success = await manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"deleted": True, "session_id": str(session_id)}
