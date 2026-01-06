"""Embedding providers for vector similarity search."""

from abc import ABC, abstractmethod
from typing import Any

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, SecretStr

logger = structlog.get_logger(__name__)


class EmbeddingConfig(BaseModel):
    """Configuration for embedding providers."""

    model: str = Field(default="text-embedding-3-small")
    dimensions: int = Field(default=1536)
    batch_size: int = Field(default=100)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimensions."""
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider using text-embedding models."""

    def __init__(
        self,
        api_key: str | SecretStr,
        config: EmbeddingConfig | None = None,
    ) -> None:
        self._config = config or EmbeddingConfig()
        key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        self._client = AsyncOpenAI(api_key=key)

    @property
    def dimensions(self) -> int:
        return self._config.dimensions

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        try:
            response = await self._client.embeddings.create(
                input=text,
                model=self._config.model,
                dimensions=self._config.dimensions,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            raise

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        # Process in batches
        for i in range(0, len(texts), self._config.batch_size):
            batch = texts[i : i + self._config.batch_size]

            try:
                response = await self._client.embeddings.create(
                    input=batch,
                    model=self._config.model,
                    dimensions=self._config.dimensions,
                )

                # Sort by index to maintain order
                sorted_data = sorted(response.data, key=lambda x: x.index)
                batch_embeddings = [item.embedding for item in sorted_data]
                all_embeddings.extend(batch_embeddings)

            except Exception as e:
                logger.error(
                    "Batch embedding generation failed",
                    batch_start=i,
                    batch_size=len(batch),
                    error=str(e),
                )
                raise

        return all_embeddings


class AnthropicEmbeddingProvider(EmbeddingProvider):
    """Anthropic embedding provider (placeholder for when available)."""

    def __init__(
        self,
        api_key: str | SecretStr,
        config: EmbeddingConfig | None = None,
    ) -> None:
        self._config = config or EmbeddingConfig()
        # Note: Anthropic doesn't have a native embedding API yet
        # This is a placeholder for future implementation
        raise NotImplementedError(
            "Anthropic embedding API is not yet available. "
            "Please use OpenAI embeddings for now."
        )

    @property
    def dimensions(self) -> int:
        return self._config.dimensions

    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError()


class CachedEmbeddingProvider(EmbeddingProvider):
    """Wrapper that adds caching to an embedding provider."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        cache: Any,  # RedisClient
        cache_ttl: int = 86400 * 7,  # 7 days default
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._ttl = cache_ttl

    @property
    def dimensions(self) -> int:
        return self._provider.dimensions

    def _cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        import hashlib

        text_hash = hashlib.sha256(text.encode()).hexdigest()[:32]
        return f"embedding:{text_hash}"

    async def embed(self, text: str) -> list[float]:
        """Get embedding from cache or generate."""
        cache_key = self._cache_key(text)

        # Try cache first
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Generate and cache
        embedding = await self._provider.embed(text)
        await self._cache.set(cache_key, embedding, ttl=self._ttl)

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings from cache or generate."""
        results: list[list[float] | None] = [None] * len(texts)
        to_generate: list[tuple[int, str]] = []

        # Check cache for each text
        for i, text in enumerate(texts):
            cache_key = self._cache_key(text)
            cached = await self._cache.get(cache_key)
            if cached is not None:
                results[i] = cached
            else:
                to_generate.append((i, text))

        # Generate missing embeddings
        if to_generate:
            indices = [idx for idx, _ in to_generate]
            texts_to_embed = [text for _, text in to_generate]

            embeddings = await self._provider.embed_batch(texts_to_embed)

            # Cache and store results
            for (idx, text), embedding in zip(to_generate, embeddings):
                cache_key = self._cache_key(text)
                await self._cache.set(cache_key, embedding, ttl=self._ttl)
                results[idx] = embedding

        return [r for r in results if r is not None]


def create_embedding_provider(
    provider: str = "openai",
    api_key: str | SecretStr | None = None,
    config: EmbeddingConfig | None = None,
) -> EmbeddingProvider:
    """Factory function to create embedding providers.

    Args:
        provider: Provider name ('openai' or 'anthropic').
        api_key: API key for the provider.
        config: Embedding configuration.

    Returns:
        Configured embedding provider.
    """
    if api_key is None:
        raise ValueError("API key is required for embedding provider")

    match provider.lower():
        case "openai":
            return OpenAIEmbeddingProvider(api_key, config)
        case "anthropic":
            return AnthropicEmbeddingProvider(api_key, config)
        case _:
            raise ValueError(f"Unknown embedding provider: {provider}")
