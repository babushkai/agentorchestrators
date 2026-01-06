"""Agent definition and configuration models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent lifecycle status."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    TERMINATED = "terminated"


class ModelProvider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    BEDROCK = "bedrock"
    LOCAL = "local"


class ModelConfig(BaseModel):
    """LLM model configuration."""

    provider: ModelProvider = ModelProvider.ANTHROPIC
    model_id: str = "claude-sonnet-4-20250514"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    stop_sequences: list[str] = Field(default_factory=list)
    extra_params: dict[str, Any] = Field(default_factory=dict)


class ToolConfig(BaseModel):
    """Tool configuration for an agent."""

    tool_id: str
    name: str
    description: str
    parameters_schema: dict[str, Any]  # JSON Schema
    required_permissions: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=30, gt=0)
    retry_count: int = Field(default=0, ge=0)
    retry_delay_seconds: float = Field(default=1.0, ge=0)


class MemoryConfig(BaseModel):
    """Memory configuration for an agent."""

    # Short-term memory (conversation context)
    short_term_enabled: bool = True
    short_term_max_messages: int = Field(default=50, gt=0)

    # Long-term memory (persistent storage)
    long_term_enabled: bool = False
    long_term_provider: str | None = None  # "redis", "postgresql", "vector"

    # Shared memory (between agents)
    shared_memory_enabled: bool = False
    shared_memory_namespace: str | None = None


class AgentConstraints(BaseModel):
    """Operational constraints for an agent."""

    max_iterations: int = Field(default=25, gt=0)
    max_execution_time_seconds: int = Field(default=300, gt=0)
    max_tokens_per_task: int = Field(default=100000, gt=0)
    max_tool_calls_per_iteration: int = Field(default=10, gt=0)
    allowed_tools: list[str] | None = None  # None means all tools allowed
    denied_tools: list[str] = Field(default_factory=list)


class AgentDefinition(BaseModel):
    """Complete agent definition."""

    model_config = {"populate_by_name": True}

    agent_id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=1)
    backstory: str | None = None

    # Configuration
    llm_config: ModelConfig = Field(default_factory=ModelConfig)
    tools: list[ToolConfig] = Field(default_factory=list)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    constraints: AgentConstraints = Field(default_factory=AgentConstraints)

    # Routing
    capabilities: set[str] = Field(default_factory=set)

    # Metadata
    tenant_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_system_prompt(self) -> str:
        """Generate the system prompt for the agent."""
        parts = [
            f"You are {self.name}, a {self.role}.",
            f"\nYour goal: {self.goal}",
        ]

        if self.backstory:
            parts.append(f"\nBackground: {self.backstory}")

        if self.tools:
            tool_names = [t.name for t in self.tools]
            parts.append(f"\nYou have access to the following tools: {', '.join(tool_names)}")

        return "\n".join(parts)


class AgentInstance(BaseModel):
    """Runtime instance of an agent."""

    instance_id: UUID = Field(default_factory=uuid4)
    agent_definition_id: UUID
    status: AgentStatus = AgentStatus.IDLE

    # Current execution
    current_task_id: UUID | None = None
    worker_id: str | None = None

    # Lifecycle
    started_at: datetime | None = None
    last_heartbeat: datetime | None = None

    # Metrics
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_tokens_used: int = 0
    total_execution_time_ms: float = 0.0

    def is_available(self) -> bool:
        """Check if the agent is available for new tasks."""
        return self.status == AgentStatus.IDLE and self.current_task_id is None

    def record_task_completion(
        self,
        tokens_used: int,
        execution_time_ms: float,
        success: bool,
    ) -> None:
        """Record task completion metrics."""
        if success:
            self.tasks_completed += 1
        else:
            self.tasks_failed += 1
        self.total_tokens_used += tokens_used
        self.total_execution_time_ms += execution_time_ms
