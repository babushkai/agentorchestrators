"""Health check endpoints."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: datetime
    version: str
    environment: str
    checks: dict[str, Any]


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    ready: bool
    checks: dict[str, bool]


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """
    Basic health check endpoint.

    Returns the current health status of the service.
    This endpoint is typically used by load balancers for health probes.
    """
    from agent_orchestrator import __version__

    settings = request.app.state.settings

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        version=__version__,
        environment=settings.environment,
        checks={},
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check(request: Request) -> ReadinessResponse:
    """
    Readiness check endpoint.

    Verifies that all required dependencies are available and the service
    is ready to accept traffic.
    """
    checks: dict[str, bool] = {}
    all_ready = True

    # Check Redis
    try:
        if hasattr(request.app.state, "redis") and request.app.state.redis:
            await request.app.state.redis.ping()
            checks["redis"] = True
        else:
            checks["redis"] = False
            all_ready = False
    except Exception:
        checks["redis"] = False
        all_ready = False

    # Check NATS
    try:
        if hasattr(request.app.state, "nats") and request.app.state.nats:
            checks["nats"] = request.app.state.nats.is_connected
        else:
            checks["nats"] = False
            all_ready = False
    except Exception:
        checks["nats"] = False
        all_ready = False

    return ReadinessResponse(ready=all_ready, checks=checks)


@router.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """
    Liveness check endpoint.

    Simple endpoint that returns OK if the service is running.
    Used by Kubernetes liveness probes.
    """
    return {"status": "ok"}


@router.get("/metrics")
async def metrics() -> Response:
    """
    Prometheus metrics endpoint.

    Exposes application metrics in Prometheus format.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
