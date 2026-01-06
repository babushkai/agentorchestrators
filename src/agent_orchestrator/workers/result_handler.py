"""Result handler service that updates task status in Redis."""

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from agent_orchestrator.config import Settings
from agent_orchestrator.infrastructure.cache.redis_client import RedisClient, get_redis_client
from agent_orchestrator.infrastructure.messaging.nats_client import NATSClient, get_nats_client

logger = structlog.get_logger(__name__)


class ResultHandler:
    """
    Handles task results from NATS and updates Redis.

    Subscribes to RESULTS.* events and updates task status in Redis
    so the API can retrieve current task states.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._nats: NATSClient | None = None
        self._redis: RedisClient | None = None
        self._running = False

    async def start(self) -> None:
        """Start the result handler service."""
        logger.info("Starting result handler service")

        self._nats = await get_nats_client(self._settings.nats)
        self._redis = await get_redis_client(self._settings.redis)
        self._running = True

        # Subscribe to result events
        await self._nats.subscribe(
            "RESULTS.completed",
            queue="result-handlers",
            handler=self._handle_completed,
            durable="result-handler-completed",
        )

        await self._nats.subscribe(
            "RESULTS.failed",
            queue="result-handlers",
            handler=self._handle_failed,
            durable="result-handler-failed",
        )

        # Subscribe to task events for status updates
        await self._nats.subscribe(
            "TASKS.started",
            queue="result-handlers",
            handler=self._handle_started,
            durable="result-handler-started",
        )

        logger.info("Result handler service started")

        # Keep running
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the result handler service."""
        logger.info("Stopping result handler service")
        self._running = False

        if self._nats:
            await self._nats.close()
        if self._redis:
            await self._redis.close()

    async def _handle_completed(self, data: dict[str, Any]) -> None:
        """Handle task completion event."""
        task_id = data.get("task_id")
        if not task_id:
            return

        logger.info("Task completed", task_id=task_id)

        # Update task in Redis
        task_data = await self._redis.get(f"task:{task_id}")
        if task_data:
            task_data["status"] = "completed"
            task_data["completed_at"] = datetime.now(timezone.utc).isoformat()
            task_data["result"] = data.get("result")
            task_data["assigned_agent_id"] = data.get("agent_id")
            await self._redis.set(f"task:{task_id}", task_data, ttl=86400 * 7)

            # Publish WebSocket notification
            await self._publish_ws_update("task_updated", task_data)

    async def _handle_failed(self, data: dict[str, Any]) -> None:
        """Handle task failure event."""
        task_id = data.get("task_id")
        if not task_id:
            return

        logger.warning("Task failed", task_id=task_id, error=data.get("error"))

        # Update task in Redis
        task_data = await self._redis.get(f"task:{task_id}")
        if task_data:
            task_data["status"] = "failed"
            task_data["completed_at"] = datetime.now(timezone.utc).isoformat()
            task_data["error"] = data.get("error")
            await self._redis.set(f"task:{task_id}", task_data, ttl=86400 * 7)

            # Publish WebSocket notification
            await self._publish_ws_update("task_updated", task_data)

    async def _handle_started(self, data: dict[str, Any]) -> None:
        """Handle task started event."""
        task_id = data.get("task_id")
        if not task_id:
            return

        logger.info("Task started", task_id=task_id, worker_id=data.get("worker_id"))

        # Update task in Redis
        task_data = await self._redis.get(f"task:{task_id}")
        if task_data:
            task_data["status"] = "running"
            task_data["started_at"] = datetime.now(timezone.utc).isoformat()
            task_data["assigned_agent_id"] = data.get("agent_id")
            await self._redis.set(f"task:{task_id}", task_data, ttl=86400 * 7)

            # Publish WebSocket notification
            await self._publish_ws_update("task_updated", task_data)

    async def _publish_ws_update(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish WebSocket update via NATS."""
        if self._nats:
            await self._nats.publish(
                "WEBSOCKET.broadcast",
                {
                    "event": event_type,
                    "data": data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )


async def run_result_handler(settings: Settings) -> None:
    """Run the result handler service."""
    handler = ResultHandler(settings)

    try:
        await handler.start()
    except KeyboardInterrupt:
        await handler.stop()
