"""OpenTelemetry setup and configuration."""

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from agent_orchestrator.config import TelemetrySettings

logger = structlog.get_logger(__name__)


def setup_telemetry(settings: TelemetrySettings) -> None:
    """Setup OpenTelemetry tracing."""
    if not settings.enabled:
        logger.info("Telemetry disabled")
        return

    logger.info(
        "Setting up OpenTelemetry",
        service_name=settings.service_name,
        endpoint=settings.exporter_otlp_endpoint,
    )

    # Create resource with service name
    resource = Resource(attributes={SERVICE_NAME: settings.service_name})

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Create OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.exporter_otlp_endpoint,
        insecure=settings.exporter_otlp_insecure,
    )

    # Add span processor
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Set the tracer provider
    trace.set_tracer_provider(provider)

    # Instrument FastAPI
    FastAPIInstrumentor().instrument()

    # Instrument HTTPX (for LLM API calls)
    HTTPXClientInstrumentor().instrument()

    logger.info("OpenTelemetry setup complete")


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer for a module."""
    return trace.get_tracer(name)


# Custom span attributes for AI/LLM calls
class LLMSpanAttributes:
    """Semantic conventions for LLM spans (based on OpenTelemetry GenAI conventions)."""

    # Request attributes
    LLM_SYSTEM = "gen_ai.system"
    LLM_REQUEST_MODEL = "gen_ai.request.model"
    LLM_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
    LLM_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
    LLM_REQUEST_TOP_P = "gen_ai.request.top_p"

    # Response attributes
    LLM_RESPONSE_ID = "gen_ai.response.id"
    LLM_RESPONSE_MODEL = "gen_ai.response.model"
    LLM_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"

    # Token usage
    LLM_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
    LLM_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

    # Agent-specific attributes
    AGENT_ID = "agent.id"
    AGENT_NAME = "agent.name"
    AGENT_ROLE = "agent.role"
    TASK_ID = "task.id"
    WORKFLOW_ID = "workflow.id"
    TOOL_NAME = "tool.name"
