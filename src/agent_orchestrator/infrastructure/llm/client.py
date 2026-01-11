"""Unified LLM client with provider selection and circuit breaker."""

from collections.abc import AsyncIterator
from typing import Any

import structlog
from circuitbreaker import circuit
from anthropic import RateLimitError as AnthropicRateLimitError
from openai import RateLimitError as OpenAIRateLimitError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from agent_orchestrator.config import LLMSettings
from agent_orchestrator.core.agents.definition import ModelProvider
from agent_orchestrator.infrastructure.llm.providers.anthropic import AnthropicProvider
from agent_orchestrator.infrastructure.llm.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
)
from agent_orchestrator.infrastructure.llm.providers.local import LocalProvider
from agent_orchestrator.infrastructure.llm.providers.openai import OpenAIProvider
from agent_orchestrator.infrastructure.llm.providers.openrouter import OpenRouterProvider

logger = structlog.get_logger(__name__)


def _is_rate_limit_error(error: BaseException) -> bool:
    """Check if error is a rate limit error from any provider."""
    return isinstance(error, (OpenAIRateLimitError, AnthropicRateLimitError))


class LLMClient:
    """Unified LLM client with provider routing and resilience patterns."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._providers: dict[str, LLMProvider] = {}
        self._fallback_provider_name: str | None = None
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
            api_key = self._settings.openai_api_key.get_secret_value()

            # Check if it's an OpenRouter key (starts with sk-or-)
            if api_key.startswith("sk-or-"):
                self._providers["openrouter"] = OpenRouterProvider(
                    api_key=api_key,
                    timeout=self._settings.timeout,
                    max_retries=self._settings.max_retries,
                )
                logger.info("OpenRouter provider initialized")
            else:
                self._providers["openai"] = OpenAIProvider(
                    api_key=api_key,
                    timeout=self._settings.timeout,
                    max_retries=self._settings.max_retries,
                )
                logger.info("OpenAI provider initialized")

        # Initialize local provider if enabled
        if self._settings.local.enabled:
            self._providers["local"] = LocalProvider(
                backend=self._settings.local.backend,
                base_url=self._settings.local.base_url,
                model=self._settings.local.default_model,
                timeout=self._settings.local.timeout,
                max_retries=self._settings.local.max_retries,
            )
            logger.info(
                "Local LLM provider initialized",
                backend=self._settings.local.backend,
                model=self._settings.local.default_model,
            )

        # Set fallback provider if configured and available
        if self._settings.fallback.enabled:
            if self._settings.fallback.fallback_provider in self._providers:
                self._fallback_provider_name = self._settings.fallback.fallback_provider
                logger.info(
                    "Fallback provider configured",
                    fallback_provider=self._fallback_provider_name,
                )
            else:
                logger.warning(
                    "Fallback enabled but provider not available",
                    fallback_provider=self._settings.fallback.fallback_provider,
                    available_providers=list(self._providers.keys()),
                )

    def get_provider(self, provider: ModelProvider | str) -> LLMProvider:
        """Get a provider by name."""
        provider_name = provider.value if isinstance(provider, ModelProvider) else provider
        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' not configured")
        return self._providers[provider_name]

    def _get_fallback_model(self, provider_name: str) -> str:
        """Get the default model for a fallback provider."""
        if provider_name == "local" and self._settings.local.default_model:
            return self._settings.local.default_model
        return self._settings.default_model

    def _should_fallback(self, error: Exception, provider_name: str) -> bool:
        """Determine if we should fallback based on the error type."""
        if not self._settings.fallback.enabled or not self._fallback_provider_name:
            return False

        # Prevent fallback to same provider
        if provider_name == self._fallback_provider_name:
            return False

        if _is_rate_limit_error(error):
            return self._settings.fallback.fallback_on_rate_limit

        return False

    async def _complete_with_fallback(
        self,
        messages: list[LLMMessage],
        provider_name: str,
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | dict[str, Any] | None,
        stop_sequences: list[str] | None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Complete with automatic fallback on rate limit."""
        llm_provider = self.get_provider(provider_name)

        try:
            response = await llm_provider.complete(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                stop_sequences=stop_sequences,
                **kwargs,
            )
            return response

        except Exception as e:
            if not _is_rate_limit_error(e) or not self._should_fallback(e, provider_name):
                raise

            # Log and execute fallback
            fallback_model = self._get_fallback_model(self._fallback_provider_name)  # type: ignore[arg-type]

            logger.warning(
                "Rate limit hit, falling back to alternative provider",
                original_provider=provider_name,
                original_model=model,
                fallback_provider=self._fallback_provider_name,
                fallback_model=fallback_model,
                error=str(e),
            )

            fallback_provider = self.get_provider(self._fallback_provider_name)  # type: ignore[arg-type]

            return await fallback_provider.complete(
                messages=messages,
                model=fallback_model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                stop_sequences=stop_sequences,
                **kwargs,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(lambda e: not _is_rate_limit_error(e)),
    )
    @circuit(failure_threshold=5, recovery_timeout=30)
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
        enable_fallback: bool = True,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion with automatic provider routing and fallback."""
        provider_name = provider or self._settings.default_provider
        if isinstance(provider_name, ModelProvider):
            provider_name = provider_name.value
        model_id = model or self._settings.default_model
        temp = temperature if temperature is not None else self._settings.default_temperature
        tokens = max_tokens or self._settings.default_max_tokens

        logger.debug(
            "LLM completion request",
            provider=provider_name,
            model=model_id,
            message_count=len(messages),
            fallback_enabled=enable_fallback and self._fallback_provider_name is not None,
        )

        if enable_fallback and self._fallback_provider_name:
            response = await self._complete_with_fallback(
                messages=messages,
                provider_name=provider_name,
                model=model_id,
                temperature=temp,
                max_tokens=tokens,
                tools=tools,
                tool_choice=tool_choice,
                stop_sequences=stop_sequences,
                **kwargs,
            )
        else:
            llm_provider = self.get_provider(provider_name)
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
        enable_fallback: bool = True,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion with optional fallback."""
        provider_name = provider or self._settings.default_provider
        if isinstance(provider_name, ModelProvider):
            provider_name = provider_name.value
        model_id = model or self._settings.default_model
        temp = temperature if temperature is not None else self._settings.default_temperature
        tokens = max_tokens or self._settings.default_max_tokens

        llm_provider = self.get_provider(provider_name)

        logger.debug(
            "LLM stream request",
            provider=provider_name,
            model=model_id,
        )

        try:
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
        except Exception as e:
            if not _is_rate_limit_error(e) or not enable_fallback or not self._should_fallback(e, provider_name):
                raise

            fallback_model = self._get_fallback_model(self._fallback_provider_name)  # type: ignore[arg-type]
            logger.warning(
                "Rate limit hit during streaming, falling back",
                original_provider=provider_name,
                fallback_provider=self._fallback_provider_name,
                fallback_model=fallback_model,
            )

            fallback_provider = self.get_provider(self._fallback_provider_name)  # type: ignore[arg-type]
            async for chunk in fallback_provider.stream(
                messages=messages,
                model=fallback_model,
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
