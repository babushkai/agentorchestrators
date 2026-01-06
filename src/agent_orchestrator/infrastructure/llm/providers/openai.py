"""OpenAI LLM provider."""

import time
from collections.abc import AsyncIterator
from typing import Any

import structlog
from openai import AsyncOpenAI

from agent_orchestrator.infrastructure.llm.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ToolCall,
)

logger = structlog.get_logger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider implementation."""

    def __init__(
        self,
        api_key: str,
        timeout: float = 120.0,
        max_retries: int = 3,
        base_url: str | None = None,
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            base_url=base_url,
        )

    @property
    def name(self) -> str:
        return "openai"

    def _convert_messages(
        self,
        messages: list[LLMMessage],
    ) -> list[dict[str, Any]]:
        """Convert messages to OpenAI format."""
        converted: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "tool":
                converted.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )
            elif msg.role == "assistant" and msg.tool_calls:
                # Convert assistant message with tool calls
                message: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": tc.function,
                        }
                        for tc in msg.tool_calls
                    ],
                }
                converted.append(message)
            else:
                # Skip assistant messages with empty content (they had tool calls not stored in memory)
                if msg.role == "assistant" and not msg.content:
                    continue
                converted.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                    }
                )

        return converted

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
        converted_messages = self._convert_messages(messages)

        start_time = time.perf_counter()

        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": converted_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if tools:
            request_kwargs["tools"] = tools

        if tool_choice:
            request_kwargs["tool_choice"] = tool_choice

        if stop_sequences:
            request_kwargs["stop"] = stop_sequences

        response = await self._client.chat.completions.create(**request_kwargs)

        latency_ms = (time.perf_counter() - start_time) * 1000

        choice = response.choices[0]
        message = choice.message

        # Extract tool calls
        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        type=tc.type,
                        function={
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    )
                )

        return LLMResponse(
            content=message.content,
            model=response.model,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "stop",
            latency_ms=latency_ms,
            tool_calls=tool_calls,
        )

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
        converted_messages = self._convert_messages(messages)

        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": converted_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        if tools:
            request_kwargs["tools"] = tools

        if stop_sequences:
            request_kwargs["stop"] = stop_sequences

        stream = await self._client.chat.completions.create(**request_kwargs)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
