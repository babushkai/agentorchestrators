"""Conversation session management."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

from agent_orchestrator.infrastructure.cache.redis_client import RedisClient

logger = structlog.get_logger(__name__)


class SessionStatus(str, Enum):
    """Session status."""

    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    EXPIRED = "expired"


class ConversationMessage(BaseModel):
    """A message in a conversation."""

    id: UUID = Field(default_factory=uuid4)
    role: str  # user, assistant, system, tool
    content: str
    name: str | None = None  # For tool messages
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None  # For assistant tool calls
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationSession(BaseModel):
    """A conversation session."""

    id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    tenant_id: str = "default"
    status: SessionStatus = SessionStatus.ACTIVE
    title: str | None = None
    system_prompt_override: str | None = None
    max_history_messages: int = Field(default=50)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: datetime | None = None
    message_count: int = 0


class SessionManager:
    """Manages conversation sessions using Redis."""

    def __init__(
        self,
        redis: RedisClient,
        default_ttl_seconds: int = 86400 * 7,  # 7 days
    ) -> None:
        """Initialize session manager.

        Args:
            redis: Redis client.
            default_ttl_seconds: Default session TTL.
        """
        self._redis = redis
        self._default_ttl = default_ttl_seconds

    def _session_key(self, session_id: UUID) -> str:
        """Get Redis key for session."""
        return f"session:{session_id}"

    def _messages_key(self, session_id: UUID) -> str:
        """Get Redis key for session messages."""
        return f"session:{session_id}:messages"

    async def create_session(
        self,
        agent_id: UUID,
        tenant_id: str = "default",
        title: str | None = None,
        system_prompt_override: str | None = None,
        max_history_messages: int = 50,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationSession:
        """Create a new conversation session.

        Args:
            agent_id: Agent ID for this session.
            tenant_id: Tenant ID.
            title: Optional session title.
            system_prompt_override: Override system prompt for this session.
            max_history_messages: Maximum messages to keep in context.
            metadata: Optional metadata.

        Returns:
            Created session.
        """
        session = ConversationSession(
            agent_id=agent_id,
            tenant_id=tenant_id,
            title=title,
            system_prompt_override=system_prompt_override,
            max_history_messages=max_history_messages,
            metadata=metadata or {},
        )

        await self._save_session(session)

        logger.info(
            "Session created",
            session_id=str(session.id),
            agent_id=str(agent_id),
        )

        return session

    async def _save_session(self, session: ConversationSession) -> None:
        """Save session to Redis."""
        data = session.model_dump(mode="json")
        # Convert UUIDs to strings for JSON serialization
        data["id"] = str(session.id)
        data["agent_id"] = str(session.agent_id)

        await self._redis.set(
            self._session_key(session.id),
            data,
            ttl=self._default_ttl,
        )

    async def get_session(self, session_id: UUID) -> ConversationSession | None:
        """Get session by ID.

        Args:
            session_id: Session ID.

        Returns:
            Session if found, None otherwise.
        """
        data = await self._redis.get(self._session_key(session_id))
        if not data:
            return None

        # Convert strings back to UUIDs
        data["id"] = UUID(data["id"])
        data["agent_id"] = UUID(data["agent_id"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["last_activity_at"] = datetime.fromisoformat(data["last_activity_at"])
        if data.get("closed_at"):
            data["closed_at"] = datetime.fromisoformat(data["closed_at"])

        return ConversationSession(**data)

    async def update_activity(self, session_id: UUID) -> None:
        """Update session last activity timestamp.

        Args:
            session_id: Session ID.
        """
        session = await self.get_session(session_id)
        if session:
            session.last_activity_at = datetime.now(timezone.utc)
            await self._save_session(session)

    async def close_session(self, session_id: UUID) -> bool:
        """Close a session.

        Args:
            session_id: Session ID.

        Returns:
            True if closed, False if not found.
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        session.status = SessionStatus.CLOSED
        session.closed_at = datetime.now(timezone.utc)
        await self._save_session(session)

        logger.info("Session closed", session_id=str(session_id))
        return True

    async def add_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        name: str | None = None,
        tool_call_id: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationMessage:
        """Add a message to a session.

        Args:
            session_id: Session ID.
            role: Message role (user, assistant, system, tool).
            content: Message content.
            name: Tool name (for tool messages).
            tool_call_id: Tool call ID (for tool results).
            tool_calls: Tool calls (for assistant messages).
            metadata: Optional metadata.

        Returns:
            Created message.
        """
        message = ConversationMessage(
            role=role,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            tool_calls=tool_calls,
            metadata=metadata or {},
        )

        # Add to message list
        message_data = message.model_dump(mode="json")
        message_data["id"] = str(message.id)

        await self._redis.rpush(self._messages_key(session_id), message_data)

        # Update session activity and message count
        session = await self.get_session(session_id)
        if session:
            session.message_count += 1
            session.last_activity_at = datetime.now(timezone.utc)

            # Generate title from first user message if not set
            if not session.title and role == "user":
                session.title = content[:50] + ("..." if len(content) > 50 else "")

            await self._save_session(session)

        return message

    async def get_messages(
        self,
        session_id: UUID,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ConversationMessage]:
        """Get messages for a session.

        Args:
            session_id: Session ID.
            limit: Maximum messages to return.
            offset: Number of messages to skip from the end.

        Returns:
            List of messages.
        """
        key = self._messages_key(session_id)

        if limit:
            # Get last N messages
            start = -(offset + limit) if offset else -limit
            end = -(offset + 1) if offset else -1
            data = await self._redis.lrange(key, start, end)
        else:
            data = await self._redis.lrange(key, 0, -1)

        messages = []
        for item in data:
            item["id"] = UUID(item["id"])
            item["created_at"] = datetime.fromisoformat(item["created_at"])
            messages.append(ConversationMessage(**item))

        return messages

    async def get_context_messages(
        self,
        session_id: UUID,
        max_messages: int | None = None,
    ) -> list[ConversationMessage]:
        """Get messages for LLM context.

        Args:
            session_id: Session ID.
            max_messages: Override max messages from session config.

        Returns:
            List of messages for context.
        """
        session = await self.get_session(session_id)
        if not session:
            return []

        limit = max_messages or session.max_history_messages
        return await self.get_messages(session_id, limit=limit)

    async def clear_messages(self, session_id: UUID) -> int:
        """Clear all messages for a session.

        Args:
            session_id: Session ID.

        Returns:
            Number of messages cleared.
        """
        key = self._messages_key(session_id)
        count = await self._redis.client.llen(key)
        await self._redis.delete(key)

        # Update session message count
        session = await self.get_session(session_id)
        if session:
            session.message_count = 0
            await self._save_session(session)

        logger.info(
            "Session messages cleared",
            session_id=str(session_id),
            count=count,
        )

        return count

    async def list_sessions(
        self,
        tenant_id: str | None = None,
        agent_id: UUID | None = None,
        status: SessionStatus | None = None,
        limit: int = 50,
    ) -> list[ConversationSession]:
        """List sessions with optional filters.

        Note: This is a scan operation and may be slow with many sessions.
        For production, consider using a database for session metadata.

        Args:
            tenant_id: Filter by tenant.
            agent_id: Filter by agent.
            status: Filter by status.
            limit: Maximum sessions to return.

        Returns:
            List of matching sessions.
        """
        sessions = []

        # Scan for session keys
        cursor = 0
        while True:
            cursor, keys = await self._redis.client.scan(
                cursor=cursor,
                match="session:*",
                count=100,
            )

            for key in keys:
                # Skip message keys
                if b":messages" in key:
                    continue

                session_id_str = key.decode().replace("session:", "")
                try:
                    session_id = UUID(session_id_str)
                    session = await self.get_session(session_id)

                    if session:
                        # Apply filters
                        if tenant_id and session.tenant_id != tenant_id:
                            continue
                        if agent_id and session.agent_id != agent_id:
                            continue
                        if status and session.status != status:
                            continue

                        sessions.append(session)

                        if len(sessions) >= limit:
                            return sessions
                except ValueError:
                    continue

            if cursor == 0:
                break

        return sessions

    async def delete_session(self, session_id: UUID) -> bool:
        """Delete a session and all its messages.

        Args:
            session_id: Session ID.

        Returns:
            True if deleted, False if not found.
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        # Delete session and messages
        await self._redis.delete(self._session_key(session_id))
        await self._redis.delete(self._messages_key(session_id))

        # Clean up file references
        await self._redis.delete(f"session:{session_id}:files")

        logger.info("Session deleted", session_id=str(session_id))
        return True
