"""FastAPI dependency injection."""

from typing import Annotated

from fastapi import Depends, Request

from agent_orchestrator.config import Settings, get_settings
from agent_orchestrator.infrastructure.cache.redis_client import RedisClient
from agent_orchestrator.infrastructure.messaging.nats_client import NATSClient
from agent_orchestrator.infrastructure.storage.object_store import ObjectStore


def get_settings_dep() -> Settings:
    """Get application settings."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


async def get_redis(request: Request) -> RedisClient:
    """Get Redis client from app state."""
    return request.app.state.redis


RedisDep = Annotated[RedisClient, Depends(get_redis)]


async def get_nats(request: Request) -> NATSClient:
    """Get NATS client from app state."""
    return request.app.state.nats


NATSDep = Annotated[NATSClient, Depends(get_nats)]


async def get_object_store(request: Request) -> ObjectStore:
    """Get object store from app state."""
    return request.app.state.object_store


ObjectStoreDep = Annotated[ObjectStore, Depends(get_object_store)]
