"""SQLAlchemy ORM models."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from agent_orchestrator.core.agents.definition import AgentStatus
from agent_orchestrator.core.workflows.models import TaskStatus, WorkflowStatus
from agent_orchestrator.infrastructure.persistence.database import Base


class AgentDefinitionModel(Base):
    """SQLAlchemy model for agent definitions."""

    __tablename__ = "agent_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String(100), nullable=False, index=True, default="default")
    name = Column(String(100), nullable=False)
    role = Column(String(200), nullable=False)
    goal = Column(Text, nullable=False)
    backstory = Column(Text, nullable=True)
    model_config = Column(JSONB, nullable=False, default={})
    tools = Column(JSONB, nullable=False, default=[])
    memory_config = Column(JSONB, nullable=False, default={})
    constraints = Column(JSONB, nullable=False, default={})
    capabilities = Column(JSONB, nullable=False, default=[])
    metadata_ = Column("metadata", JSONB, nullable=False, default={})
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    instances = relationship("AgentInstanceModel", back_populates="definition")


class AgentInstanceModel(Base):
    """SQLAlchemy model for agent instances."""

    __tablename__ = "agent_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    definition_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    worker_id = Column(String(100), nullable=True, index=True)
    status = Column(
        Enum(AgentStatus, name="agent_status"),
        nullable=False,
        default=AgentStatus.IDLE,
    )
    current_task_id = Column(UUID(as_uuid=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    tasks_completed = Column(Integer, nullable=False, default=0)
    tasks_failed = Column(Integer, nullable=False, default=0)
    total_tokens_used = Column(Integer, nullable=False, default=0)
    total_execution_time_ms = Column(Float, nullable=False, default=0.0)

    # Relationships
    definition = relationship("AgentDefinitionModel", back_populates="instances")


class TaskModel(Base):
    """SQLAlchemy model for tasks."""

    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String(100), nullable=False, index=True, default="default")
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    input_data = Column(JSONB, nullable=False, default={})
    required_capabilities = Column(JSONB, nullable=False, default=[])
    priority = Column(Integer, nullable=False, default=1)
    status = Column(
        Enum(TaskStatus, name="task_status"),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
    )
    assigned_agent_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    parent_workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_step_id = Column(String(100), nullable=True)
    timeout_seconds = Column(Integer, nullable=False, default=300)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    result = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)


class WorkflowDefinitionModel(Base):
    """SQLAlchemy model for workflow definitions."""

    __tablename__ = "workflow_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String(100), nullable=False, index=True, default="default")
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    version = Column(String(20), nullable=False, default="1.0.0")
    steps = Column(JSONB, nullable=False, default=[])
    input_schema = Column(JSONB, nullable=True)
    output_schema = Column(JSONB, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=False, default={})
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    executions = relationship("WorkflowExecutionModel", back_populates="definition")


class WorkflowExecutionModel(Base):
    """SQLAlchemy model for workflow executions."""

    __tablename__ = "workflow_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id = Column(String(100), nullable=False, index=True, default="default")
    status = Column(
        Enum(WorkflowStatus, name="workflow_status"),
        nullable=False,
        default=WorkflowStatus.PENDING,
        index=True,
    )
    current_step_id = Column(String(100), nullable=True)
    completed_steps = Column(JSONB, nullable=False, default=[])
    step_results = Column(JSONB, nullable=False, default={})
    failed_step_id = Column(String(100), nullable=True)
    input_data = Column(JSONB, nullable=False, default={})
    output_data = Column(JSONB, nullable=True)
    checkpoint_data = Column(JSONB, nullable=False, default={})
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)

    # Relationships
    definition = relationship("WorkflowDefinitionModel", back_populates="executions")
    tasks = relationship("TaskModel", backref="workflow_execution")
