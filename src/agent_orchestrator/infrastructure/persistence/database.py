"""Database configuration and session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from agent_orchestrator.config import DatabaseSettings

logger = structlog.get_logger(__name__)

# Naming convention for constraints
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Global engine and session factory
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_database(settings: DatabaseSettings) -> AsyncEngine:
    """Initialize the database engine and session factory."""
    global _engine, _session_factory

    logger.info("Initializing database", host=settings.host, database=settings.name)

    _engine = create_async_engine(
        settings.url,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        echo=settings.echo,
        pool_pre_ping=True,  # Enable connection health checks
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # Test connection
    async with _engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

    logger.info("Database initialized successfully")
    return _engine


async def close_database() -> None:
    """Close the database engine."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("Database connection closed")


def get_engine() -> AsyncEngine:
    """Get the database engine."""
    if _engine is None:
        raise RuntimeError("Database not initialized")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the session factory."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized")
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_session_dep() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with get_session() as session:
        yield session
