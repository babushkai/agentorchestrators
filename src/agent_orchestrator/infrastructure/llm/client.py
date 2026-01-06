"""Unified LLM client with provider selection and circuit breaker."""

from collections.abc import AsyncIterator
from typing import Any

import structlog
from circuitbreaker import circuit
from tenacity import retry, stop_after_attempt, wait_exponential

from agent_orchestrator.config import LLMSettings
from agent_orchestrator.core.agents.definition import ModelProvider
from agent_orchestrator.infrastructure.llm.providers.anthropic import AnthropicProvider
from agent_orchestrator.infrastructure.llm.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
)
from agent_orchestrator.infrastructure.llm.providers.openai import OpenAIProvider

logger = structlog.get_logger(__name__)


class LLMClient:
    """Unified LLM client with provider routing and resilience patterns."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._providers: dict[str, LLMProvider] = {}
        self._init_providers()

    def _init_providers(self) -> None:
        """Initialize configured providers."""
        if self._settings.anthropic_api_key:
            self._providers["anthropic"] = AnthropicProvider(
                api_key=self._settings.anthropic_api_key.get_secret_value(),
                timeout=self._settings.timeout,
                max_retries=self._settings.max_retries,
            )
            logger.info("Anthropic provider initialized")

        if self._settings.openai_api_key:
            self._providers["openai"] = OpenAIProvider(
                api_key=self._settings.openai_api_key.get_secret_value(),
                timeout=self._settings.timeout,
                max_retries=self._settings.max_retries,
            )
            logger.info("OpenAI provider initialized")

    def get_provider(self, provider: ModelProvider | str) -> LLMProvider:
        """Get a provider by name."""
        provider_name = provider.value if isinstance(provider, ModelProvider) else provider
        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' not configured")
        return self._providers[provider_name]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    @circuit(failure_threshold=5, recovery_timeout=60)
    async def complete(
        self,
        messages: list[LLMMessage],
        provider: ModelProvider | str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        stop_sequences: list[str] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion with automatic provider routing."""
        provider_name = provider or self._settings.default_provider
        model_id = model or self._settings.default_model
        temp = temperature if temperature is not None else self._settings.default_temperature
        tokens = max_tokens or self._settings.default_max_tokens

        llm_provider = self.get_provider(provider_name)

        logger.debug(
            "LLM completion request",
            provider=provider_name,
            model=model_id,
            message_count=len(messages),
        )

        response = await llm_provider.complete(
            messages=messages,
            model=model_id,
            temperature=temp,
            max_tokens=tokens,
            tools=tools,
            tool_choice=tool_choice,
            stop_sequences=stop_sequences,
            **kwargs,
        )

        logger.debug(
            "LLM completion response",
            provider=provider_name,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_ms=response.latency_ms,
        )

        return response

    async def stream(
        self,
        messages: list[LLMMessage],
        provider: ModelProvider | str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        stop_sequences: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion."""
        provider_name = provider or self._settings.default_provider
        model_id = model or self._settings.default_model
        temp = temperature if temperature is not None else self._settings.default_temperature
        tokens = max_tokens or self._settings.default_max_tokens

        llm_provider = self.get_provider(provider_name)

        logger.debug(
            "LLM stream request",
            provider=provider_name,
            model=model_id,
        )

        async for chunk in llm_provider.stream(
            messages=messages,
            model=model_id,
            temperature=temp,
            max_tokens=tokens,
            tools=tools,
            stop_sequences=stop_sequences,
            **kwargs,
        ):
            yield chunk


# Global client instance
_llm_client: LLMClient | None = None


def get_llm_client(settings: LLMSettings | None = None) -> LLMClient:
    """Get or create the LLM client."""
    global _llm_client
    if _llm_client is None:
        if settings is None:
            from agent_orchestrator.config import get_settings

            settings = get_settings().llm
        _llm_client = LLMClient(settings)
    return _llm_client
