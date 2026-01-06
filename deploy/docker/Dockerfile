# Multi-stage Dockerfile for Agent Orchestrator
# Optimized for production with minimal image size

# =============================================================================
# Build stage - Install dependencies and build wheel
# =============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install pip and build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel build

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Build wheel
RUN python -m build --wheel

# Install dependencies to a target directory for copying
RUN pip install --no-cache-dir --target=/install dist/*.whl

# =============================================================================
# Runtime stage - Minimal production image
# =============================================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -g 1000 agent && useradd -u 1000 -g agent -m agent

# Copy installed packages from builder
COPY --from=builder /install /usr/local/lib/python3.12/site-packages

# Copy application code (for static files and templates)
COPY --chown=agent:agent src/agent_orchestrator/api/static /app/static

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/usr/local/lib/python3.12/site-packages \
    # Default configuration
    ENVIRONMENT=production \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    LOG_LEVEL=INFO

# Switch to non-root user
USER agent

# Expose port
EXPOSE 8000

# Use tini as init system for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command (API server)
CMD ["python", "-m", "uvicorn", "agent_orchestrator.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

# =============================================================================
# API Server variant
# =============================================================================
FROM runtime AS api

# Health check for API
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["python", "-m", "uvicorn", "agent_orchestrator.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# =============================================================================
# Worker variant
# =============================================================================
FROM runtime AS worker

# Workers don't need health check via HTTP, they use heartbeats
ENV WORKER_CONCURRENCY=5

CMD ["python", "-m", "agent_orchestrator", "worker", "--concurrency", "5"]

# =============================================================================
# Result Handler variant
# =============================================================================
FROM runtime AS result-handler

CMD ["python", "-c", "import asyncio; from agent_orchestrator.workers.result_handler import ResultHandler; from agent_orchestrator.config import get_settings; asyncio.run(ResultHandler(get_settings()).start())"]
