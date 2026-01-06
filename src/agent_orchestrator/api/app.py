"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles

from agent_orchestrator.api.middleware.error_handler import error_handler_middleware
from agent_orchestrator.api.routes import agents, conversations, files, health, tasks, websocket, workflows
from agent_orchestrator.config import Settings, get_settings
from agent_orchestrator.infrastructure.observability.telemetry import setup_telemetry

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    settings = get_settings()

    # Initialize infrastructure connections
    from agent_orchestrator.infrastructure.cache.redis_client import get_redis_client
    from agent_orchestrator.infrastructure.messaging.nats_client import get_nats_client
    from agent_orchestrator.infrastructure.persistence.database import init_database
    from agent_orchestrator.infrastructure.storage.object_store import get_object_store

    # Startup
    await init_database(settings.database)
    app.state.redis = await get_redis_client(settings.redis)
    app.state.nats = await get_nats_client(settings.nats)
    app.state.object_store = await get_object_store(settings.s3)

    # Setup WebSocket event broadcasting
    from agent_orchestrator.api.routes.websocket import setup_websocket_events

    await setup_websocket_events(app.state.nats)

    yield

    # Shutdown
    if hasattr(app.state, "redis") and app.state.redis:
        await app.state.redis.close()
    if hasattr(app.state, "nats") and app.state.nats:
        await app.state.nats.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = get_settings()

    # Setup OpenTelemetry if enabled
    if settings.telemetry.enabled:
        setup_telemetry(settings.telemetry)

    app = FastAPI(
        title="Agent Orchestrator API",
        description="A distributed AI agent orchestration system with event-driven architecture",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # Store settings in app state
    app.state.settings = settings

    # Add middleware
    _add_middleware(app, settings)

    # Include routers
    _include_routers(app)

    # Mount static files for dashboard
    _mount_static(app)

    return app


def _add_middleware(app: FastAPI, settings: Settings) -> None:
    """Add middleware to the application."""
    # Error handler middleware (should be first)
    app.middleware("http")(error_handler_middleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # OpenTelemetry instrumentation is added via setup_telemetry


def _include_routers(app: FastAPI) -> None:
    """Include API routers."""
    app.include_router(health.router, tags=["Health"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["Tasks"])
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
    app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["Workflows"])
    app.include_router(files.router, prefix="/api/v1", tags=["Files"])
    app.include_router(conversations.router, prefix="/api/v1", tags=["Conversations"])
    app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])

    # Also include routes without /api/v1 prefix for simpler dashboard access
    app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"], include_in_schema=False)
    app.include_router(agents.router, prefix="/agents", tags=["Agents"], include_in_schema=False)
    app.include_router(workflows.router, prefix="/workflows", tags=["Workflows"], include_in_schema=False)
    app.include_router(files.router, tags=["Files"], include_in_schema=False)
    app.include_router(conversations.router, tags=["Conversations"], include_in_schema=False)


def _mount_static(app: FastAPI) -> None:
    """Mount static files for the dashboard."""
    from fastapi.responses import FileResponse

    @app.get("/", include_in_schema=False)
    async def serve_dashboard() -> FileResponse:
        """Serve the dashboard."""
        return FileResponse(STATIC_DIR / "index.html")

    # Mount static directory
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Create app instance for uvicorn
app = create_app()
