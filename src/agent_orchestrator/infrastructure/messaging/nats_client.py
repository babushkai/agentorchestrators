"""NATS JetStream client wrapper."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import nats
import orjson
import structlog
from nats.aio.client import Client
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, DeliverPolicy, RetentionPolicy, StreamConfig

from agent_orchestrator.config import NATSSettings

logger = structlog.get_logger(__name__)


class NATSClient:
    """NATS JetStream client wrapper with connection management."""

    # Stream configurations
    STREAMS: dict[str, StreamConfig] = {
        "TASKS": StreamConfig(
            name="TASKS",
            subjects=["TASKS.*"],
            retention=RetentionPolicy.LIMITS,
            max_msgs=100000,
            max_age=7 * 24 * 60 * 60,  # 7 days in seconds
        ),
        "AGENTS": StreamConfig(
            name="AGENTS",
            subjects=["AGENTS.*", "AGENTS.commands.*", "AGENTS.events.>"],
            retention=RetentionPolicy.LIMITS,
            max_msgs=100000,
            max_age=7 * 24 * 60 * 60,
        ),
        "WORKFLOWS": StreamConfig(
            name="WORKFLOWS",
            subjects=["WORKFLOWS.*", "WORKFLOWS.execution.*", "WORKFLOWS.events.*"],
            retention=RetentionPolicy.LIMITS,
            max_msgs=100000,
            max_age=30 * 24 * 60 * 60,  # 30 days
        ),
        "RESULTS": StreamConfig(
            name="RESULTS",
            subjects=["RESULTS.*"],
            retention=RetentionPolicy.LIMITS,
            max_msgs=100000,
            max_age=7 * 24 * 60 * 60,
        ),
        "WORKERS": StreamConfig(
            name="WORKERS",
            subjects=["WORKERS.*"],
            retention=RetentionPolicy.LIMITS,
            max_msgs=10000,
            max_age=60 * 60,  # 1 hour for heartbeats
        ),
        "WEBSOCKET": StreamConfig(
            name="WEBSOCKET",
            subjects=["WEBSOCKET.*"],
            retention=RetentionPolicy.LIMITS,
            max_msgs=1000,
            max_age=60,  # 1 minute for real-time events
        ),
    }

    def __init__(self, settings: NATSSettings) -> None:
        self._settings = settings
        self._client: Client | None = None
        self._js: JetStreamContext | None = None
        self._subscriptions: list[Any] = []

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._client is not None and self._client.is_connected

    @property
    def client(self) -> Client:
        """Get the NATS client."""
        if self._client is None:
            raise RuntimeError("NATS client not connected")
        return self._client

    @property
    def js(self) -> JetStreamContext:
        """Get the JetStream context."""
        if self._js is None:
            raise RuntimeError("NATS JetStream not initialized")
        return self._js

    async def connect(self) -> None:
        """Connect to NATS and initialize JetStream."""
        logger.info("Connecting to NATS", servers=self._settings.servers)

        connect_opts: dict[str, Any] = {
            "servers": self._settings.servers,
            "connect_timeout": self._settings.connect_timeout,
            "max_reconnect_attempts": self._settings.max_reconnect_attempts,
            "reconnect_time_wait": 1,
            "error_cb": self._on_error,
            "disconnected_cb": self._on_disconnected,
            "reconnected_cb": self._on_reconnected,
        }

        if self._settings.user and self._settings.password:
            connect_opts["user"] = self._settings.user
            connect_opts["password"] = self._settings.password.get_secret_value()
        elif self._settings.token:
            connect_opts["token"] = self._settings.token.get_secret_value()

        self._client = await nats.connect(**connect_opts)
        self._js = self._client.jetstream()

        # Initialize streams
        await self._init_streams()

        logger.info("Connected to NATS successfully")

    async def _init_streams(self) -> None:
        """Initialize JetStream streams."""
        for name, config in self.STREAMS.items():
            try:
                await self.js.add_stream(config)
                logger.debug("Stream created or updated", stream=name)
            except Exception as e:
                # Stream might already exist, try to update
                try:
                    await self.js.update_stream(config)
                    logger.debug("Stream updated", stream=name)
                except Exception:
                    logger.warning("Failed to create/update stream", stream=name, error=str(e))

    async def _on_error(self, e: Exception) -> None:
        """Handle NATS errors."""
        logger.error("NATS error", error=str(e))

    async def _on_disconnected(self) -> None:
        """Handle disconnection."""
        logger.warning("Disconnected from NATS")

    async def _on_reconnected(self) -> None:
        """Handle reconnection."""
        logger.info("Reconnected to NATS")

    async def close(self) -> None:
        """Close the NATS connection."""
        if self._client:
            # Unsubscribe from all subscriptions
            for sub in self._subscriptions:
                try:
                    await sub.unsubscribe()
                except Exception:
                    pass

            await self._client.drain()
            logger.info("NATS connection closed")

    async def publish(
        self,
        subject: str,
        data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> None:
        """Publish a message to a subject."""
        payload = orjson.dumps(data)

        if self._js:
            await self._js.publish(subject, payload, headers=headers)
        else:
            await self.client.publish(subject, payload, headers=headers)

        logger.debug("Message published", subject=subject)

    async def subscribe(
        self,
        subject: str,
        queue: str,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
        durable: str | None = None,
    ) -> None:
        """Subscribe to a subject with a handler."""

        async def message_handler(msg: Any) -> None:
            try:
                data = orjson.loads(msg.data)
                await handler(data)
                await msg.ack()
            except Exception as e:
                logger.error(
                    "Error processing message",
                    subject=msg.subject,
                    error=str(e),
                )
                # Negative ack to requeue
                await msg.nak()

        config = ConsumerConfig(
            durable_name=durable,
            deliver_policy=DeliverPolicy.ALL,
            ack_wait=30,  # seconds
            max_deliver=3,
        )

        sub = await self.js.subscribe(
            subject,
            queue=queue,
            cb=message_handler,
            config=config,
        )
        self._subscriptions.append(sub)
        logger.info("Subscribed to subject", subject=subject, queue=queue)

    async def request(
        self,
        subject: str,
        data: dict[str, Any],
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        """Send a request and wait for a response."""
        payload = orjson.dumps(data)
        response = await self.client.request(subject, payload, timeout=timeout)
        return orjson.loads(response.data)


# Global client instance
_nats_client: NATSClient | None = None


async def get_nats_client(settings: NATSSettings) -> NATSClient:
    """Get or create the NATS client."""
    global _nats_client
    if _nats_client is None:
        _nats_client = NATSClient(settings)
        await _nats_client.connect()
    return _nats_client
