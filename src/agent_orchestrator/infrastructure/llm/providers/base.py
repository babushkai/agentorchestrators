"""Base LLM provider interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    """A message in an LLM conversation."""

    role: str  # "user", "assistant", "system", "tool"
    content: str | list[dict[str, Any]]
    name: str | None = None  # For tool messages
    tool_call_id: str | None = None  # For tool results
    tool_calls: list["ToolCall"] | None = None  # For assistant tool calls


class ToolCall(BaseModel):
    """A tool call in an LLM response."""

    id: str
    type: str = "function"
    function: dict[str, Any]  # {"name": str, "arguments": str (JSON)}


class LLMResponse(BaseModel):
    """Response from an LLM provider."""

    content: str | None
    model: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str  # "stop", "tool_calls", "length", etc.
    latency_ms: float
    tool_calls: list[ToolCall] = Field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        stop_sequences: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        stop_sequences: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion."""
        ...
