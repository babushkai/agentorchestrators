"""Anthropic Claude LLM provider."""

import time
from collections.abc import AsyncIterator
from typing import Any

import structlog
from anthropic import AsyncAnthropic
from anthropic.types import ContentBlock, Message, ToolUseBlock

from agent_orchestrator.infrastructure.llm.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ToolCall,
)

logger = structlog.get_logger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider implementation."""

    def __init__(
        self,
        api_key: str,
        timeout: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        self._client = AsyncAnthropic(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

    @property
    def name(self) -> str:
        return "anthropic"

    def _convert_messages(
        self,
        messages: list[LLMMessage],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert messages to Anthropic format, extracting system message."""
        system_message: str | None = None
        converted: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content if isinstance(msg.content, str) else str(msg.content)
            elif msg.role == "tool":
                # Convert tool result to Anthropic format
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )
            elif msg.role == "assistant" and msg.tool_calls:
                # Convert assistant message with tool calls
                content: list[dict[str, Any]] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    import json

                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.function["name"],
                            "input": json.loads(tc.function["arguments"]),
                        }
                    )
                converted.append({"role": "assistant", "content": content})
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

        return system_message, converted

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert OpenAI-style tools to Anthropic format."""
        converted = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                converted.append(
                    {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
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
        system_message, converted_messages = self._convert_messages(messages)

        start_time = time.perf_counter()

        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": converted_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system_message:
            request_kwargs["system"] = system_message

        if tools:
            request_kwargs["tools"] = self._convert_tools(tools)

        if tool_choice:
            if isinstance(tool_choice, str):
                if tool_choice == "auto":
                    request_kwargs["tool_choice"] = {"type": "auto"}
                elif tool_choice == "required":
                    request_kwargs["tool_choice"] = {"type": "any"}
                elif tool_choice == "none":
                    pass  # Don't send tools
            elif isinstance(tool_choice, dict):
                request_kwargs["tool_choice"] = tool_choice

        if stop_sequences:
            request_kwargs["stop_sequences"] = stop_sequences

        response: Message = await self._client.messages.create(**request_kwargs)

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Extract content and tool calls
        content_text: str | None = None
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                import json

                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        type="function",
                        function={
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    )
                )

        return LLMResponse(
            content=content_text,
            model=response.model,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            finish_reason="tool_calls" if tool_calls else response.stop_reason or "stop",
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
        system_message, converted_messages = self._convert_messages(messages)

        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": converted_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system_message:
            request_kwargs["system"] = system_message

        if tools:
            request_kwargs["tools"] = self._convert_tools(tools)

        if stop_sequences:
            request_kwargs["stop_sequences"] = stop_sequences

        async with self._client.messages.stream(**request_kwargs) as stream:
            async for text in stream.text_stream:
                yield text
