"""WebSocket endpoints for real-time streaming."""

import asyncio
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = structlog.get_logger(__name__)

# Background task for NATS subscription
_nats_listener_task: asyncio.Task[None] | None = None


class ConnectionManager:
    """Manages WebSocket connections for real-time streaming."""

    def __init__(self) -> None:
        # Map of task_id -> list of websockets
        self._task_connections: dict[UUID, list[WebSocket]] = {}
        # Map of agent_id -> list of websockets
        self._agent_connections: dict[UUID, list[WebSocket]] = {}
        # Global connections for all events
        self._global_connections: list[WebSocket] = []

    async def connect_task(self, websocket: WebSocket, task_id: UUID) -> None:
        """Connect a WebSocket to a task's event stream."""
        await websocket.accept()
        if task_id not in self._task_connections:
            self._task_connections[task_id] = []
        self._task_connections[task_id].append(websocket)
        logger.info("WebSocket connected to task", task_id=str(task_id))

    async def connect_agent(self, websocket: WebSocket, agent_id: UUID) -> None:
        """Connect a WebSocket to an agent's event stream."""
        await websocket.accept()
        if agent_id not in self._agent_connections:
            self._agent_connections[agent_id] = []
        self._agent_connections[agent_id].append(websocket)
        logger.info("WebSocket connected to agent", agent_id=str(agent_id))

    async def connect_global(self, websocket: WebSocket) -> None:
        """Connect a WebSocket to global event stream."""
        await websocket.accept()
        self._global_connections.append(websocket)
        logger.info("WebSocket connected to global stream")

    def disconnect_task(self, websocket: WebSocket, task_id: UUID) -> None:
        """Disconnect a WebSocket from a task's event stream."""
        if task_id in self._task_connections:
            self._task_connections[task_id] = [
                ws for ws in self._task_connections[task_id] if ws != websocket
            ]
            if not self._task_connections[task_id]:
                del self._task_connections[task_id]

    def disconnect_agent(self, websocket: WebSocket, agent_id: UUID) -> None:
        """Disconnect a WebSocket from an agent's event stream."""
        if agent_id in self._agent_connections:
            self._agent_connections[agent_id] = [
                ws for ws in self._agent_connections[agent_id] if ws != websocket
            ]
            if not self._agent_connections[agent_id]:
                del self._agent_connections[agent_id]

    def disconnect_global(self, websocket: WebSocket) -> None:
        """Disconnect a WebSocket from global event stream."""
        self._global_connections = [
            ws for ws in self._global_connections if ws != websocket
        ]

    async def broadcast_task_event(self, task_id: UUID, event: dict[str, Any]) -> None:
        """Broadcast an event to all connections watching a task."""
        connections = self._task_connections.get(task_id, [])
        await self._broadcast(connections, event)

    async def broadcast_agent_event(self, agent_id: UUID, event: dict[str, Any]) -> None:
        """Broadcast an event to all connections watching an agent."""
        connections = self._agent_connections.get(agent_id, [])
        await self._broadcast(connections, event)

    async def broadcast_global(self, event: dict[str, Any]) -> None:
        """Broadcast an event to all global connections."""
        await self._broadcast(self._global_connections, event)

    async def _broadcast(
        self, connections: list[WebSocket], event: dict[str, Any]
    ) -> None:
        """Broadcast a message to a list of connections."""
        disconnected: list[WebSocket] = []

        for websocket in connections:
            try:
                await websocket.send_json(event)
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected sockets
        for ws in disconnected:
            connections.remove(ws)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/tasks/{task_id}/stream")
async def stream_task(websocket: WebSocket, task_id: UUID) -> None:
    """
    Stream real-time events for a specific task.

    Events include:
    - task.progress: Progress updates
    - task.output: Agent output chunks
    - task.completed: Task completion
    - task.failed: Task failure
    """
    await manager.connect_task(websocket, task_id)
    try:
        while True:
            # Keep connection alive with heartbeat
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Handle client messages (e.g., ping/pong)
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        manager.disconnect_task(websocket, task_id)
        logger.info("WebSocket disconnected from task", task_id=str(task_id))


@router.websocket("/agents/{agent_id}/stream")
async def stream_agent(websocket: WebSocket, agent_id: UUID) -> None:
    """
    Stream real-time events for a specific agent.

    Events include:
    - agent.thinking: Agent reasoning steps
    - agent.tool_call: Tool invocations
    - agent.output: Generated output
    - agent.error: Errors
    """
    await manager.connect_agent(websocket, agent_id)
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        manager.disconnect_agent(websocket, agent_id)
        logger.info("WebSocket disconnected from agent", agent_id=str(agent_id))


@router.websocket("/events/stream")
async def stream_all_events(websocket: WebSocket) -> None:
    """
    Stream all system events.

    Useful for monitoring dashboards and debugging.
    Events are filtered by the client after connection.
    """
    await manager.connect_global(websocket)
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        manager.disconnect_global(websocket)
        logger.info("WebSocket disconnected from global stream")


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager."""
    return manager


async def start_nats_listener(nats_client: Any) -> None:
    """Start listening to NATS events and broadcast to WebSocket clients."""
    global _nats_listener_task

    async def handle_websocket_broadcast(data: dict[str, Any]) -> None:
        """Handle WEBSOCKET.broadcast events from NATS."""
        event_type = data.get("event")
        event_data = data.get("data", {})

        # Broadcast to all global connections
        await manager.broadcast_global({
            "type": event_type,
            "data": event_data,
            "timestamp": data.get("timestamp"),
        })

        # Also broadcast to specific task/agent if applicable
        if task_id := event_data.get("task_id"):
            try:
                await manager.broadcast_task_event(
                    UUID(task_id),
                    {"type": event_type, "data": event_data},
                )
            except ValueError:
                pass

        if agent_id := event_data.get("agent_id"):
            try:
                await manager.broadcast_agent_event(
                    UUID(agent_id),
                    {"type": event_type, "data": event_data},
                )
            except ValueError:
                pass

    async def handle_task_events(data: dict[str, Any]) -> None:
        """Handle TASKS.* events."""
        await manager.broadcast_global({
            "type": "task_event",
            "data": data,
        })

    async def handle_agent_events(data: dict[str, Any]) -> None:
        """Handle AGENTS.events.* events."""
        await manager.broadcast_global({
            "type": "agent_event",
            "data": data,
        })

    async def handle_result_events(data: dict[str, Any]) -> None:
        """Handle RESULTS.* events."""
        await manager.broadcast_global({
            "type": "result_event",
            "data": data,
        })

        # Also broadcast to specific task
        if task_id := data.get("task_id"):
            try:
                await manager.broadcast_task_event(
                    UUID(task_id),
                    {"type": "result", "data": data},
                )
            except ValueError:
                pass

    try:
        # Subscribe to WebSocket broadcast channel
        await nats_client.subscribe(
            "WEBSOCKET.broadcast",
            queue="ws-broadcasters",
            handler=handle_websocket_broadcast,
            durable="ws-broadcaster",
        )

        # Subscribe to task events
        await nats_client.subscribe(
            "TASKS.*",
            queue="ws-task-events",
            handler=handle_task_events,
            durable="ws-task-events",
        )

        # Subscribe to agent events
        await nats_client.subscribe(
            "AGENTS.events.*",
            queue="ws-agent-events",
            handler=handle_agent_events,
            durable="ws-agent-events",
        )

        # Subscribe to result events
        await nats_client.subscribe(
            "RESULTS.*",
            queue="ws-result-events",
            handler=handle_result_events,
            durable="ws-result-events",
        )

        logger.info("WebSocket NATS listener started")

        # Keep running
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        logger.error("WebSocket NATS listener error", error=str(e))


async def setup_websocket_events(nats_client: Any) -> None:
    """Setup WebSocket event broadcasting from NATS."""
    global _nats_listener_task

    if _nats_listener_task is None or _nats_listener_task.done():
        _nats_listener_task = asyncio.create_task(start_nats_listener(nats_client))
        logger.info("WebSocket event broadcaster initialized")
