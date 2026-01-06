# Agent Orchestrator

A production-ready distributed AI agent orchestrator with event-driven architecture and Kubernetes auto-scaling.

## Features

- **Multi-Agent Orchestration**: Manage and coordinate multiple AI agents
- **Event-Driven Architecture**: NATS JetStream for reliable messaging
- **Workflow Engine**: DAG-based workflows with parallel execution and saga pattern
- **Real-time Updates**: WebSocket streaming for live task progress
- **Auto-scaling**: KEDA-based worker scaling on Kubernetes
- **Observability**: OpenTelemetry, Prometheus metrics, Jaeger tracing
- **Built-in Tools**: Calculator, code execution, file operations, HTTP requests, web scraping
- **Document Processing**: Support for PDF, DOCX, and image files
- **Vector Search**: PostgreSQL with pgvector for semantic search

## Prerequisites

- **Python 3.12+** (3.13 supported)
- **Docker** and **Docker Compose** (for local infrastructure)
- **LLM API Keys** (optional for basic setup):
  - Anthropic API key (recommended)
  - OpenAI API key (alternative)

## Installation

### Option 1: Automated Setup (Recommended)

Run the development setup script:

```bash
./scripts/setup-dev.sh
```

This script will:
- Check Python version
- Create a virtual environment
- Install dependencies
- Set up pre-commit hooks
- Optionally start Docker infrastructure
- Run database migrations

### Option 2: Manual Setup

1. **Create and activate a virtual environment:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**

   ```bash
   # For development (includes dev tools)
   make dev
   
   # OR for production only
   make install
   
   # OR using pip directly
   pip install -e ".[dev]"
   ```

3. **Install pre-commit hooks (development only):**

   ```bash
   pre-commit install
   ```

## Configuration

### Environment Variables

Create a `.env` file in the project root to customize settings:

```bash
# Environment
ENVIRONMENT=development

# LLM Configuration
LLM_DEFAULT_PROVIDER=anthropic  # or "openai"
LLM_ANTHROPIC_API_KEY=your_anthropic_key_here
LLM_OPENAI_API_KEY=your_openai_key_here
LLM_DEFAULT_MODEL=claude-sonnet-4-20250514
LLM_DEFAULT_TEMPERATURE=0.7
LLM_DEFAULT_MAX_TOKENS=4096

# Database (defaults work with docker-compose)
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=orchestrator
DATABASE_PASSWORD=orchestrator_dev
DATABASE_NAME=agent_orchestrator

# NATS (defaults work with docker-compose)
NATS_SERVERS=nats://localhost:4222

# Redis (defaults work with docker-compose)
REDIS_HOST=localhost
REDIS_PORT=6379

# S3/MinIO (defaults work with docker-compose)
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET=agent-orchestrator

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false

# Telemetry
OTEL_ENABLED=true
OTEL_SERVICE_NAME=agent-orchestrator
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

**Note:** The application works with sensible defaults for local development, so a `.env` file is optional unless you need to customize settings.

## Running the Application

### 1. Start Infrastructure Services

Start all required services (NATS, PostgreSQL, Redis, MinIO, etc.):

```bash
make docker-up
# OR
docker compose up -d
```

This starts:
- **NATS** (port 4222) - Message broker with JetStream
- **PostgreSQL** (port 5432) - Database with pgvector
- **Redis** (port 6379) - Cache
- **MinIO** (port 9000) - S3-compatible object storage
- **Jaeger** (port 16686) - Distributed tracing UI
- **Prometheus** (port 9090) - Metrics collection
- **Grafana** (port 3000) - Dashboards (admin/admin)

### 2. Run Database Migrations

```bash
make migrate
# OR
alembic upgrade head
```

### 3. Start the API Server

```bash
make run
# OR
agent-orchestrator serve
# OR
uvicorn agent_orchestrator.api.app:create_app --factory --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

### 4. Start Workers

In a separate terminal, start one or more workers:

```bash
make run-worker
# OR
agent-orchestrator worker
```

Workers process tasks from the message queue. You can run multiple workers for parallel processing.

### 5. Stop Infrastructure

```bash
make docker-down
# OR
docker compose down
```

## Development

### Code Quality

```bash
# Run linting
make lint

# Format code
make format

# Type checking
mypy src
```

### Testing

```bash
# Run all tests
make test

# Run tests in parallel
make test-parallel

# Run only unit tests
make test-unit

# Run only integration tests
make test-integration
```

### Database Migrations

```bash
# Create a new migration
make migrate-create
# Then enter migration message when prompted

# Apply migrations
make migrate

# View migration history
alembic history
```

### Generate OpenAPI Spec

```bash
make openapi
```

### Clean Up

```bash
# Remove cache files and build artifacts
make clean
```

## Project Structure

```
agentorchestrators/
├── src/agent_orchestrator/     # Main application code
│   ├── api/                    # FastAPI application
│   │   ├── routes/             # API endpoints
│   │   ├── schemas/            # Request/response models
│   │   └── middleware/         # Custom middleware
│   ├── core/                   # Core business logic
│   │   ├── agents/             # Agent runtime and tools
│   │   ├── workflows/          # Workflow engine
│   │   ├── orchestration/      # Orchestrator and supervisor
│   │   └── conversation/       # Conversation management
│   ├── infrastructure/         # Infrastructure layer
│   │   ├── llm/               # LLM provider clients
│   │   ├── persistence/       # Database models and repos
│   │   ├── messaging/         # NATS client
│   │   ├── cache/             # Redis client
│   │   └── storage/           # Object storage
│   └── workers/                # Background workers
├── tests/                      # Test suite
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── e2e/                   # End-to-end tests
├── deploy/                     # Deployment configurations
│   ├── docker/                # Dockerfile
│   ├── kubernetes/            # K8s manifests with Kustomize
│   ├── prometheus/            # Prometheus config
│   └── grafana/               # Grafana provisioning
├── scripts/                    # Utility scripts
├── docker-compose.yml          # Local development infrastructure
├── pyproject.toml              # Project configuration
└── Makefile                    # Common commands
```

## Architecture

### Components

- **API Server**: FastAPI application handling HTTP/WebSocket requests
- **Orchestrator**: Coordinates agent execution and workflow management
- **Workers**: Process tasks from the message queue
  - **Agent Worker**: Executes agent tasks
  - **Workflow Worker**: Executes workflow steps
  - **Result Handler**: Processes task results
- **Message Broker**: NATS JetStream for reliable event-driven communication
- **Database**: PostgreSQL with pgvector for persistence and vector search
- **Cache**: Redis for caching and session management
- **Object Storage**: MinIO/S3 for file storage

### Key Concepts

- **Agents**: AI agents with tools and memory capabilities
- **Workflows**: DAG-based workflows with parallel execution
- **Tasks**: Individual units of work executed by agents
- **Conversations**: Multi-turn conversations with context management
- **Events**: Event-driven architecture for decoupled components

## Observability

### Metrics

- Prometheus metrics available at http://localhost:9090
- Grafana dashboards at http://localhost:3000 (admin/admin)

### Tracing

- Jaeger UI at http://localhost:16686
- OpenTelemetry traces exported to Jaeger

### Logging

- Structured logging with `structlog`
- Log level configurable via `OTEL_LOG_LEVEL`

## Deployment

### Docker

```bash
# Build Docker image
make docker-build
# OR
docker build -t agent-orchestrator:latest -f deploy/docker/Dockerfile .
```

### Kubernetes

Deployment configurations are in `deploy/kubernetes/` using Kustomize:

```bash
# Development
kubectl apply -k deploy/kubernetes/overlays/development

# Staging
kubectl apply -k deploy/kubernetes/overlays/staging

# Production
kubectl apply -k deploy/kubernetes/overlays/production
```

The Kubernetes setup includes:
- Auto-scaling with KEDA
- Horizontal Pod Autoscaling (HPA)
- Pod Disruption Budgets
- Service mesh ready

## API Usage Examples

### Create an Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "research-agent",
    "model": "claude-sonnet-4-20250514",
    "tools": ["http", "calculator"]
  }'
```

### Create a Task

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-id-here",
    "input": "Research the latest AI developments"
  }'
```

### Stream Task Updates (WebSocket)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/tasks/{task_id}');
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Task update:', update);
};
```

See http://localhost:8000/docs for complete API documentation.

## Troubleshooting

### Services not starting

- Ensure Docker is running: `docker info`
- Check service logs: `docker compose logs [service-name]`
- Verify ports are not in use

### Database connection errors

- Ensure PostgreSQL is running: `docker compose ps`
- Check database credentials in `.env`
- Verify migrations ran: `alembic current`

### Worker not processing tasks

- Verify NATS is running: `docker compose ps nats`
- Check worker logs for connection errors
- Ensure tasks are being created via API

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting: `make test && make lint`
5. Submit a pull request

## License

MIT
