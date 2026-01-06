"""Agent memory management."""

from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from agent_orchestrator.infrastructure.cache.redis_client import RedisClient


class Message(BaseModel):
    """A message in the agent's conversation history."""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    name: str | None = None  # For tool messages
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None  # For assistant messages with tool use
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryStore(ABC):
    """Abstract base class for memory storage."""

    @abstractmethod
    async def add_message(self, agent_id: UUID, task_id: UUID, message: Message) -> None:
        """Add a message to memory."""
        ...

    @abstractmethod
    async def get_messages(
        self,
        agent_id: UUID,
        task_id: UUID,
        limit: int | None = None,
    ) -> list[Message]:
        """Get messages from memory."""
        ...

    @abstractmethod
    async def clear(self, agent_id: UUID, task_id: UUID) -> None:
        """Clear memory for a task."""
        ...

    @abstractmethod
    async def get_context_window(
        self,
        agent_id: UUID,
        task_id: UUID,
        max_messages: int,
    ) -> list[Message]:
        """Get the most recent messages within the context window."""
        ...


class InMemoryStore(MemoryStore):
    """In-memory message store for development/testing."""

    def __init__(self, max_messages: int = 1000) -> None:
        self._max_messages = max_messages
        self._store: dict[str, deque[Message]] = {}

    def _key(self, agent_id: UUID, task_id: UUID) -> str:
        return f"{agent_id}:{task_id}"

    async def add_message(self, agent_id: UUID, task_id: UUID, message: Message) -> None:
        key = self._key(agent_id, task_id)
        if key not in self._store:
            self._store[key] = deque(maxlen=self._max_messages)
        self._store[key].append(message)

    async def get_messages(
        self,
        agent_id: UUID,
        task_id: UUID,
        limit: int | None = None,
    ) -> list[Message]:
        key = self._key(agent_id, task_id)
        messages = list(self._store.get(key, []))
        if limit:
            messages = messages[-limit:]
        return messages

    async def clear(self, agent_id: UUID, task_id: UUID) -> None:
        key = self._key(agent_id, task_id)
        self._store.pop(key, None)

    async def get_context_window(
        self,
        agent_id: UUID,
        task_id: UUID,
        max_messages: int,
    ) -> list[Message]:
        return await self.get_messages(agent_id, task_id, limit=max_messages)


class RedisMemoryStore(MemoryStore):
    """Redis-backed memory store for production."""

    def __init__(self, redis: RedisClient, ttl_seconds: int = 86400) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    def _key(self, agent_id: UUID, task_id: UUID) -> str:
        return f"memory:{agent_id}:{task_id}"

    async def add_message(self, agent_id: UUID, task_id: UUID, message: Message) -> None:
        key = self._key(agent_id, task_id)
        await self._redis.rpush(key, message.model_dump())
        await self._redis.expire(key, self._ttl)

    async def get_messages(
        self,
        agent_id: UUID,
        task_id: UUID,
        limit: int | None = None,
    ) -> list[Message]:
        key = self._key(agent_id, task_id)
        if limit:
            start = -limit
            end = -1
        else:
            start = 0
            end = -1
        data = await self._redis.lrange(key, start, end)
        return [Message(**item) for item in data]

    async def clear(self, agent_id: UUID, task_id: UUID) -> None:
        key = self._key(agent_id, task_id)
        await self._redis.delete(key)

    async def get_context_window(
        self,
        agent_id: UUID,
        task_id: UUID,
        max_messages: int,
    ) -> list[Message]:
        return await self.get_messages(agent_id, task_id, limit=max_messages)


class AgentMemory:
    """High-level memory manager for an agent."""

    def __init__(
        self,
        agent_id: UUID,
        store: MemoryStore,
        max_context_messages: int = 50,
    ) -> None:
        self._agent_id = agent_id
        self._store = store
        self._max_context_messages = max_context_messages
        self._current_task_id: UUID | None = None

    def set_task(self, task_id: UUID) -> None:
        """Set the current task for memory operations."""
        self._current_task_id = task_id

    async def add_user_message(self, content: str) -> None:
        """Add a user message."""
        if not self._current_task_id:
            raise ValueError("No task set")
        await self._store.add_message(
            self._agent_id,
            self._current_task_id,
            Message(role="user", content=content),
        )

    async def add_assistant_message(
        self,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add an assistant message."""
        if not self._current_task_id:
            raise ValueError("No task set")
        await self._store.add_message(
            self._agent_id,
            self._current_task_id,
            Message(role="assistant", content=content, tool_calls=tool_calls),
        )

    async def add_tool_result(
        self,
        tool_name: str,
        tool_call_id: str,
        result: str,
    ) -> None:
        """Add a tool result message."""
        if not self._current_task_id:
            raise ValueError("No task set")
        await self._store.add_message(
            self._agent_id,
            self._current_task_id,
            Message(
                role="tool",
                content=result,
                name=tool_name,
                tool_call_id=tool_call_id,
            ),
        )

    async def get_context(self) -> list[Message]:
        """Get the current context window."""
        if not self._current_task_id:
            return []
        return await self._store.get_context_window(
            self._agent_id,
            self._current_task_id,
            self._max_context_messages,
        )

    async def clear_task_memory(self) -> None:
        """Clear memory for the current task."""
        if self._current_task_id:
            await self._store.clear(self._agent_id, self._current_task_id)
