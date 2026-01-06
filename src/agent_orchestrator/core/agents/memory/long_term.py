"""Long-term memory store with PostgreSQL and vector similarity search."""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_orchestrator.infrastructure.llm.embeddings import EmbeddingProvider

logger = structlog.get_logger(__name__)


class MemoryType(str, Enum):
    """Types of agent memories."""

    CONVERSATION = "conversation"  # Conversation history
    FACT = "fact"  # Learned facts
    SUMMARY = "summary"  # Summarized content
    CONTEXT = "context"  # Task/session context
    INSTRUCTION = "instruction"  # User instructions/preferences


class Memory(BaseModel):
    """A memory entry."""

    id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    session_id: UUID | None = None
    memory_type: MemoryType
    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    access_count: int = Field(default=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    # Similarity score (set during retrieval)
    similarity: float | None = None


class LongTermMemoryStore:
    """PostgreSQL-backed long-term memory with optional vector similarity search."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialize the long-term memory store.

        Args:
            session_factory: SQLAlchemy async session factory.
            embedding_provider: Optional embedding provider for semantic search.
        """
        self._session_factory = session_factory
        self._embedding = embedding_provider

    async def store(
        self,
        agent_id: UUID,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        session_id: UUID | None = None,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
        ttl_days: int | None = None,
    ) -> UUID:
        """Store a new memory.

        Args:
            agent_id: ID of the agent.
            content: Memory content text.
            memory_type: Type of memory.
            session_id: Optional session ID for session-scoped memories.
            importance: Importance score (0.0 to 1.0).
            metadata: Optional metadata.
            ttl_days: Optional TTL in days (None for permanent).

        Returns:
            ID of the stored memory.
        """
        memory_id = uuid4()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=ttl_days) if ttl_days else None

        # Generate embedding if provider available
        embedding = None
        if self._embedding:
            try:
                embedding = await self._embedding.embed(content)
            except Exception as e:
                logger.warning("Failed to generate embedding", error=str(e))

        async with self._session_factory() as session:
            # Insert using raw SQL to handle array type properly
            await session.execute(
                """
                INSERT INTO agent_memories
                (id, agent_id, session_id, memory_type, content, embedding,
                 importance_score, access_count, metadata, created_at, expires_at)
                VALUES
                (:id, :agent_id, :session_id, :memory_type, :content, :embedding,
                 :importance_score, 0, :metadata, :created_at, :expires_at)
                """,
                {
                    "id": memory_id,
                    "agent_id": agent_id,
                    "session_id": session_id,
                    "memory_type": memory_type.value,
                    "content": content,
                    "embedding": embedding,
                    "importance_score": importance,
                    "metadata": metadata or {},
                    "created_at": now,
                    "expires_at": expires_at,
                },
            )
            await session.commit()

        logger.debug(
            "Memory stored",
            memory_id=str(memory_id),
            agent_id=str(agent_id),
            memory_type=memory_type.value,
        )

        return memory_id

    async def search_similar(
        self,
        agent_id: UUID,
        query: str,
        limit: int = 10,
        threshold: float = 0.7,
        memory_types: list[MemoryType] | None = None,
        session_id: UUID | None = None,
        include_expired: bool = False,
    ) -> list[Memory]:
        """Search for similar memories using vector similarity.

        Args:
            agent_id: ID of the agent.
            query: Query text for similarity search.
            limit: Maximum number of results.
            threshold: Minimum similarity score (0.0 to 1.0).
            memory_types: Filter by memory types.
            session_id: Filter by session ID.
            include_expired: Include expired memories.

        Returns:
            List of matching memories sorted by similarity.
        """
        if not self._embedding:
            logger.warning("No embedding provider configured, falling back to text search")
            return await self.search_text(
                agent_id, query, limit, memory_types, session_id, include_expired
            )

        # Generate query embedding
        try:
            query_embedding = await self._embedding.embed(query)
        except Exception as e:
            logger.warning("Failed to generate query embedding", error=str(e))
            return await self.search_text(
                agent_id, query, limit, memory_types, session_id, include_expired
            )

        async with self._session_factory() as session:
            # Build query with cosine similarity
            # Note: This uses array operations - for production, use pgvector extension
            sql = """
                SELECT
                    id, agent_id, session_id, memory_type, content,
                    importance_score, access_count, last_accessed_at,
                    metadata, created_at, expires_at,
                    1 - (
                        (SELECT SUM(a * b) FROM unnest(embedding, :query_embedding) AS t(a, b))
                        / (
                            SQRT(SUM(e * e)) * SQRT(SUM(q * q))
                        )
                    ) AS similarity
                FROM agent_memories,
                     LATERAL (SELECT unnest(embedding) AS e) AS e_vals,
                     LATERAL (SELECT unnest(:query_embedding::float[]) AS q) AS q_vals
                WHERE agent_id = :agent_id
                  AND embedding IS NOT NULL
            """

            params: dict[str, Any] = {
                "agent_id": agent_id,
                "query_embedding": query_embedding,
            }

            # Add filters
            if not include_expired:
                sql += " AND (expires_at IS NULL OR expires_at > :now)"
                params["now"] = datetime.now(timezone.utc)

            if memory_types:
                sql += " AND memory_type = ANY(:memory_types)"
                params["memory_types"] = [mt.value for mt in memory_types]

            if session_id:
                sql += " AND session_id = :session_id"
                params["session_id"] = session_id

            sql += f"""
                GROUP BY id, agent_id, session_id, memory_type, content,
                         importance_score, access_count, last_accessed_at,
                         metadata, created_at, expires_at
                HAVING similarity >= :threshold
                ORDER BY similarity DESC
                LIMIT :limit
            """
            params["threshold"] = 1 - threshold  # Convert to distance
            params["limit"] = limit

            result = await session.execute(sql, params)
            rows = result.fetchall()

            memories = []
            for row in rows:
                memories.append(
                    Memory(
                        id=row.id,
                        agent_id=row.agent_id,
                        session_id=row.session_id,
                        memory_type=MemoryType(row.memory_type),
                        content=row.content,
                        importance_score=row.importance_score,
                        access_count=row.access_count,
                        metadata=row.metadata,
                        created_at=row.created_at,
                        expires_at=row.expires_at,
                        similarity=1 - row.similarity,  # Convert back to similarity
                    )
                )

            # Update access counts
            if memories:
                memory_ids = [m.id for m in memories]
                await session.execute(
                    """
                    UPDATE agent_memories
                    SET access_count = access_count + 1,
                        last_accessed_at = :now
                    WHERE id = ANY(:ids)
                    """,
                    {"ids": memory_ids, "now": datetime.now(timezone.utc)},
                )
                await session.commit()

            return memories

    async def search_text(
        self,
        agent_id: UUID,
        query: str,
        limit: int = 10,
        memory_types: list[MemoryType] | None = None,
        session_id: UUID | None = None,
        include_expired: bool = False,
    ) -> list[Memory]:
        """Search memories by text matching (fallback when embeddings unavailable).

        Args:
            agent_id: ID of the agent.
            query: Query text.
            limit: Maximum number of results.
            memory_types: Filter by memory types.
            session_id: Filter by session ID.
            include_expired: Include expired memories.

        Returns:
            List of matching memories.
        """
        async with self._session_factory() as session:
            sql = """
                SELECT
                    id, agent_id, session_id, memory_type, content,
                    importance_score, access_count, last_accessed_at,
                    metadata, created_at, expires_at
                FROM agent_memories
                WHERE agent_id = :agent_id
                  AND content ILIKE :query_pattern
            """

            params: dict[str, Any] = {
                "agent_id": agent_id,
                "query_pattern": f"%{query}%",
            }

            if not include_expired:
                sql += " AND (expires_at IS NULL OR expires_at > :now)"
                params["now"] = datetime.now(timezone.utc)

            if memory_types:
                sql += " AND memory_type = ANY(:memory_types)"
                params["memory_types"] = [mt.value for mt in memory_types]

            if session_id:
                sql += " AND session_id = :session_id"
                params["session_id"] = session_id

            sql += " ORDER BY importance_score DESC, created_at DESC LIMIT :limit"
            params["limit"] = limit

            result = await session.execute(sql, params)
            rows = result.fetchall()

            return [
                Memory(
                    id=row.id,
                    agent_id=row.agent_id,
                    session_id=row.session_id,
                    memory_type=MemoryType(row.memory_type),
                    content=row.content,
                    importance_score=row.importance_score,
                    access_count=row.access_count,
                    metadata=row.metadata,
                    created_at=row.created_at,
                    expires_at=row.expires_at,
                )
                for row in rows
            ]

    async def get_recent(
        self,
        agent_id: UUID,
        limit: int = 10,
        memory_types: list[MemoryType] | None = None,
        session_id: UUID | None = None,
    ) -> list[Memory]:
        """Get most recent memories.

        Args:
            agent_id: ID of the agent.
            limit: Maximum number of results.
            memory_types: Filter by memory types.
            session_id: Filter by session ID.

        Returns:
            List of recent memories.
        """
        async with self._session_factory() as session:
            sql = """
                SELECT
                    id, agent_id, session_id, memory_type, content,
                    importance_score, access_count, last_accessed_at,
                    metadata, created_at, expires_at
                FROM agent_memories
                WHERE agent_id = :agent_id
                  AND (expires_at IS NULL OR expires_at > :now)
            """

            params: dict[str, Any] = {
                "agent_id": agent_id,
                "now": datetime.now(timezone.utc),
            }

            if memory_types:
                sql += " AND memory_type = ANY(:memory_types)"
                params["memory_types"] = [mt.value for mt in memory_types]

            if session_id:
                sql += " AND session_id = :session_id"
                params["session_id"] = session_id

            sql += " ORDER BY created_at DESC LIMIT :limit"
            params["limit"] = limit

            result = await session.execute(sql, params)
            rows = result.fetchall()

            return [
                Memory(
                    id=row.id,
                    agent_id=row.agent_id,
                    session_id=row.session_id,
                    memory_type=MemoryType(row.memory_type),
                    content=row.content,
                    importance_score=row.importance_score,
                    access_count=row.access_count,
                    metadata=row.metadata,
                    created_at=row.created_at,
                    expires_at=row.expires_at,
                )
                for row in rows
            ]

    async def delete(self, memory_id: UUID) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: ID of the memory to delete.

        Returns:
            True if deleted, False if not found.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                "DELETE FROM agent_memories WHERE id = :id",
                {"id": memory_id},
            )
            await session.commit()
            return result.rowcount > 0

    async def delete_session_memories(self, session_id: UUID) -> int:
        """Delete all memories for a session.

        Args:
            session_id: Session ID.

        Returns:
            Number of deleted memories.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                "DELETE FROM agent_memories WHERE session_id = :session_id",
                {"session_id": session_id},
            )
            await session.commit()
            return result.rowcount

    async def cleanup_expired(self) -> int:
        """Delete expired memories.

        Returns:
            Number of deleted memories.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                """
                DELETE FROM agent_memories
                WHERE expires_at IS NOT NULL AND expires_at < :now
                """,
                {"now": datetime.now(timezone.utc)},
            )
            await session.commit()

            count = result.rowcount
            if count > 0:
                logger.info("Cleaned up expired memories", count=count)

            return count

    async def update_importance(
        self,
        memory_id: UUID,
        importance: float,
    ) -> bool:
        """Update memory importance score.

        Args:
            memory_id: Memory ID.
            importance: New importance score (0.0 to 1.0).

        Returns:
            True if updated, False if not found.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                """
                UPDATE agent_memories
                SET importance_score = :importance
                WHERE id = :id
                """,
                {"id": memory_id, "importance": importance},
            )
            await session.commit()
            return result.rowcount > 0
