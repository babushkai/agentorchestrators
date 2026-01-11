"""Local LLM provider for Ollama and LM Studio."""

from typing import Any, Literal

from agent_orchestrator.infrastructure.llm.providers.openai import OpenAIProvider


class LocalProvider(OpenAIProvider):
    """
    Local LLM provider supporting Ollama and LM Studio.

    Both services expose OpenAI-compatible APIs:
    - Ollama: http://localhost:11434/v1
    - LM Studio: http://localhost:1234/v1
    """

    def __init__(
        self,
        backend: Literal["ollama", "lmstudio"] = "ollama",
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 300.0,
        max_retries: int = 1,
        **kwargs: Any,
    ) -> None:
        """Initialize local LLM provider.

        Args:
            backend: Which local LLM backend to use ("ollama" or "lmstudio")
            base_url: Override the default base URL for the backend
            model: Default model to use (e.g., "llama3.2:3b" for Ollama)
            timeout: Request timeout in seconds (longer default for local models)
            max_retries: Number of retries on transient errors
        """
        self._backend = backend
        self._default_model = model

        # Determine base URL
        if base_url:
            self._base_url = base_url
        elif backend == "ollama":
            self._base_url = "http://localhost:11434/v1"
        else:  # lmstudio
            self._base_url = "http://localhost:1234/v1"

        # Local LLMs don't need API keys, but OpenAI client requires one
        # Initialize with placeholder key
        super().__init__(
            api_key="local-no-key-needed",
            base_url=self._base_url,
            timeout=timeout,
            max_retries=max_retries,
        )

    @property
    def name(self) -> str:
        return "local"

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def default_model(self) -> str | None:
        return self._default_model
