"""Agent supervisor for lifecycle management."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog

from agent_orchestrator.core.agents import AgentInstance, AgentStatus

logger = structlog.get_logger(__name__)


class AgentSupervisor:
    """
    Supervisor for managing agent health and lifecycle.

    Responsibilities:
    - Health monitoring via heartbeats
    - Automatic restart of failed agents
    - Scaling recommendations
    - Resource cleanup
    """

    def __init__(
        self,
        heartbeat_timeout: timedelta = timedelta(seconds=30),
        check_interval: float = 5.0,
    ) -> None:
        self._heartbeat_timeout = heartbeat_timeout
        self._check_interval = check_interval
        self._agents: dict[UUID, AgentInstance] = {}
        self._running = False
        self._check_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the supervisor."""
        logger.info("Starting agent supervisor")
        self._running = True
        self._check_task = asyncio.create_task(self._health_check_loop())

    async def stop(self) -> None:
        """Stop the supervisor."""
        logger.info("Stopping agent supervisor")
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass

    def register(self, instance: AgentInstance) -> None:
        """Register an agent instance for monitoring."""
        self._agents[instance.instance_id] = instance
        logger.debug(
            "Agent registered with supervisor",
            instance_id=str(instance.instance_id),
        )

    def unregister(self, instance_id: UUID) -> None:
        """Unregister an agent instance."""
        self._agents.pop(instance_id, None)

    async def heartbeat(self, instance_id: UUID) -> None:
        """Record a heartbeat from an agent."""
        instance = self._agents.get(instance_id)
        if instance:
            instance.last_heartbeat = datetime.now(timezone.utc)

    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        while self._running:
            try:
                await self._check_health()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health check error", error=str(e))
                await asyncio.sleep(self._check_interval)

    async def _check_health(self) -> None:
        """Check health of all registered agents."""
        now = datetime.now(timezone.utc)
        unhealthy: list[UUID] = []

        for instance_id, instance in self._agents.items():
            if instance.status == AgentStatus.TERMINATED:
                continue

            if instance.last_heartbeat:
                time_since_heartbeat = now - instance.last_heartbeat
                if time_since_heartbeat > self._heartbeat_timeout:
                    unhealthy.append(instance_id)
                    logger.warning(
                        "Agent heartbeat timeout",
                        instance_id=str(instance_id),
                        last_heartbeat=instance.last_heartbeat.isoformat(),
                    )

        # Handle unhealthy agents
        for instance_id in unhealthy:
            await self._handle_unhealthy_agent(instance_id)

    async def _handle_unhealthy_agent(self, instance_id: UUID) -> None:
        """Handle an unhealthy agent."""
        instance = self._agents.get(instance_id)
        if not instance:
            return

        instance.status = AgentStatus.ERROR

        # If agent was running a task, it needs to be reassigned
        if instance.current_task_id:
            logger.warning(
                "Agent failed with active task",
                instance_id=str(instance_id),
                task_id=str(instance.current_task_id),
            )
            # The orchestrator should handle task reassignment

    def get_scaling_recommendation(self) -> dict[str, Any]:
        """
        Get scaling recommendations based on current state.

        Returns recommendations for KEDA or other autoscalers.
        """
        total = len(self._agents)
        running = sum(
            1 for a in self._agents.values() if a.status == AgentStatus.RUNNING
        )
        idle = sum(1 for a in self._agents.values() if a.status == AgentStatus.IDLE)
        error = sum(1 for a in self._agents.values() if a.status == AgentStatus.ERROR)

        utilization = running / total if total > 0 else 0

        recommendation = "stable"
        if utilization > 0.8 and idle == 0:
            recommendation = "scale_up"
        elif utilization < 0.2 and total > 1:
            recommendation = "scale_down"

        return {
            "total_agents": total,
            "running_agents": running,
            "idle_agents": idle,
            "error_agents": error,
            "utilization": utilization,
            "recommendation": recommendation,
        }

    def get_agent_status(self, instance_id: UUID) -> dict[str, Any] | None:
        """Get detailed status of an agent."""
        instance = self._agents.get(instance_id)
        if not instance:
            return None

        return {
            "instance_id": str(instance.instance_id),
            "status": instance.status.value,
            "current_task_id": str(instance.current_task_id)
            if instance.current_task_id
            else None,
            "started_at": instance.started_at.isoformat() if instance.started_at else None,
            "last_heartbeat": instance.last_heartbeat.isoformat()
            if instance.last_heartbeat
            else None,
            "tasks_completed": instance.tasks_completed,
            "tasks_failed": instance.tasks_failed,
            "total_tokens_used": instance.total_tokens_used,
        }
