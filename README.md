# Agent Orchestrator

A production-ready distributed AI agent orchestrator with event-driven architecture and Kubernetes auto-scaling.

## Features

- **Multi-Agent Orchestration**: Manage and coordinate multiple AI agents
- **Event-Driven Architecture**: NATS JetStream for reliable messaging
- **Workflow Engine**: DAG-based workflows with parallel execution and saga pattern
- **Real-time Updates**: WebSocket streaming for live task progress
- **Auto-scaling**: KEDA-based worker scaling on Kubernetes
- **Observability**: OpenTelemetry, Prometheus metrics, Jaeger tracing

## Quick Start

```bash
# Install dependencies
pip install -e .

# Start infrastructure
docker compose up -d

# Run API server
agent-orchestrator serve

# Run worker
agent-orchestrator worker
```

## License

MIT
