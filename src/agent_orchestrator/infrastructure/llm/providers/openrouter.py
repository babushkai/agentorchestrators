"""OpenRouter LLM provider (uses OpenAI-compatible API with free models)."""

from typing import Any

from openai import AsyncOpenAI

from agent_orchestrator.infrastructure.llm.providers.openai import OpenAIProvider


class OpenRouterProvider(OpenAIProvider):
    """
    OpenRouter provider using OpenAI-compatible API.

    OpenRouter provides access to many models including free ones.
    Get your API key from: https://openrouter.ai/keys

    Free models include:
    - meta-llama/llama-3.2-3b-instruct:free
    - google/gemma-2-9b-it:free
    - microsoft/phi-3-mini-128k-instruct:free
    """

    def __init__(self, api_key: str, **kwargs: Any) -> None:
        """Initialize OpenRouter provider."""
        # Override base URL to point to OpenRouter
        super().__init__(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            **kwargs
        )

        # Update client with OpenRouter-specific headers
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/yourusername/agentorchestrators",
                "X-Title": "Agent Orchestrator",
            }
        )
