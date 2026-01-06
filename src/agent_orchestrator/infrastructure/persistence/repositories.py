"""Repository pattern implementations for data access."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_orchestrator.core.agents import AgentDefinition, AgentInstance, AgentStatus
from agent_orchestrator.core.workflows import Task, TaskStatus, WorkflowDefinition, WorkflowExecution
from agent_orchestrator.infrastructure.persistence.models import (
    AgentDefinitionModel,
    AgentInstanceModel,
    TaskModel,
    WorkflowDefinitionModel,
    WorkflowExecutionModel,
)

T = TypeVar("T")
M = TypeVar("M")


class Repository(ABC, Generic[T, M]):
    """Abstract base repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @abstractmethod
    async def get(self, id: UUID) -> T | None:
        """Get entity by ID."""
        ...

    @abstractmethod
    async def save(self, entity: T) -> T:
        """Save entity."""
        ...

    @abstractmethod
    async def delete(self, id: UUID) -> bool:
        """Delete entity by ID."""
        ...


class AgentDefinitionRepository(Repository[AgentDefinition, AgentDefinitionModel]):
    """Repository for agent definitions."""

    async def get(self, id: UUID) -> AgentDefinition | None:
        """Get agent definition by ID."""
        stmt = select(AgentDefinitionModel).where(AgentDefinitionModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_entity(model)

    async def get_by_tenant(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AgentDefinition]:
        """Get agent definitions by tenant."""
        stmt = (
            select(AgentDefinitionModel)
            .where(AgentDefinitionModel.tenant_id == tenant_id)
            .order_by(AgentDefinitionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_entity(m) for m in models]

    async def save(self, entity: AgentDefinition) -> AgentDefinition:
        """Save agent definition."""
        model = AgentDefinitionModel(
            id=entity.agent_id,
            tenant_id=entity.tenant_id or "default",
            name=entity.name,
            role=entity.role,
            goal=entity.goal,
            backstory=entity.backstory,
            model_config=entity.llm_config.model_dump(),
            tools=[t.model_dump() for t in entity.tools],
            memory_config=entity.memory.model_dump(),
            constraints=entity.constraints.model_dump(),
            capabilities=list(entity.capabilities),
            metadata_=entity.metadata,
        )

        self._session.add(model)
        await self._session.flush()

        return entity

    async def delete(self, id: UUID) -> bool:
        """Delete agent definition."""
        stmt = select(AgentDefinitionModel).where(AgentDefinitionModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            await self._session.delete(model)
            return True
        return False

    def _to_entity(self, model: AgentDefinitionModel) -> AgentDefinition:
        """Convert model to entity."""
        from agent_orchestrator.core.agents import (
            AgentConstraints,
            MemoryConfig,
            ModelConfig,
            ToolConfig,
        )

        return AgentDefinition(
            agent_id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            role=model.role,
            goal=model.goal,
            backstory=model.backstory,
            llm_config=ModelConfig(**model.model_config),
            tools=[ToolConfig(**t) for t in model.tools],
            memory=MemoryConfig(**model.memory_config),
            constraints=AgentConstraints(**model.constraints),
            capabilities=set(model.capabilities),
            metadata=model.metadata_,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class TaskRepository(Repository[Task, TaskModel]):
    """Repository for tasks."""

    async def get(self, id: UUID) -> Task | None:
        """Get task by ID."""
        stmt = select(TaskModel).where(TaskModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_entity(model)

    async def get_pending(
        self,
        tenant_id: str,
        limit: int = 100,
    ) -> list[Task]:
        """Get pending tasks."""
        stmt = (
            select(TaskModel)
            .where(TaskModel.tenant_id == tenant_id)
            .where(TaskModel.status == TaskStatus.PENDING)
            .order_by(TaskModel.priority.desc(), TaskModel.created_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_entity(m) for m in models]

    async def save(self, entity: Task) -> Task:
        """Save task."""
        model = TaskModel(
            id=entity.task_id,
            tenant_id=entity.tenant_id,
            name=entity.name,
            description=entity.description,
            input_data=entity.input_data,
            required_capabilities=list(entity.required_capabilities),
            priority=entity.priority.value,
            status=entity.status,
            assigned_agent_id=entity.assigned_agent_id,
            parent_workflow_id=entity.parent_workflow_id,
            parent_step_id=entity.parent_step_id,
            timeout_seconds=entity.timeout_seconds,
            retry_count=entity.retry_count,
            max_retries=entity.max_retries,
            started_at=entity.started_at,
            completed_at=entity.completed_at,
            result=entity.result,
            error=entity.error,
        )

        self._session.add(model)
        await self._session.flush()

        return entity

    async def update_status(
        self,
        id: UUID,
        status: TaskStatus,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        """Update task status."""
        values: dict = {"status": status}

        if status == TaskStatus.RUNNING:
            values["started_at"] = datetime.now(timezone.utc)
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            values["completed_at"] = datetime.now(timezone.utc)

        if result is not None:
            values["result"] = result
        if error is not None:
            values["error"] = error

        stmt = update(TaskModel).where(TaskModel.id == id).values(**values)
        await self._session.execute(stmt)

    async def delete(self, id: UUID) -> bool:
        """Delete task."""
        stmt = select(TaskModel).where(TaskModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            await self._session.delete(model)
            return True
        return False

    def _to_entity(self, model: TaskModel) -> Task:
        """Convert model to entity."""
        from agent_orchestrator.core.workflows import TaskPriority

        return Task(
            task_id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            description=model.description,
            input_data=model.input_data,
            required_capabilities=set(model.required_capabilities),
            priority=TaskPriority(model.priority),
            status=model.status,
            assigned_agent_id=model.assigned_agent_id,
            parent_workflow_id=model.parent_workflow_id,
            parent_step_id=model.parent_step_id,
            timeout_seconds=model.timeout_seconds,
            retry_count=model.retry_count,
            max_retries=model.max_retries,
            created_at=model.created_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            result=model.result,
            error=model.error,
        )


class WorkflowExecutionRepository(Repository[WorkflowExecution, WorkflowExecutionModel]):
    """Repository for workflow executions."""

    async def get(self, id: UUID) -> WorkflowExecution | None:
        """Get workflow execution by ID."""
        stmt = select(WorkflowExecutionModel).where(WorkflowExecutionModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_entity(model)

    async def save(self, entity: WorkflowExecution) -> WorkflowExecution:
        """Save workflow execution."""
        model = WorkflowExecutionModel(
            id=entity.execution_id,
            workflow_id=entity.workflow_definition_id,
            tenant_id=entity.tenant_id,
            status=entity.status,
            current_step_id=entity.current_step_id,
            completed_steps=entity.completed_steps,
            step_results=entity.step_results,
            failed_step_id=entity.failed_step_id,
            input_data=entity.input_data,
            output_data=entity.output_data,
            checkpoint_data=entity.checkpoint_data,
            started_at=entity.started_at,
            completed_at=entity.completed_at,
            error=entity.error,
        )

        self._session.add(model)
        await self._session.flush()

        return entity

    async def update_checkpoint(
        self,
        id: UUID,
        checkpoint_data: dict,
        current_step_id: str | None = None,
        completed_steps: list[str] | None = None,
    ) -> None:
        """Update workflow checkpoint."""
        values: dict = {"checkpoint_data": checkpoint_data}

        if current_step_id is not None:
            values["current_step_id"] = current_step_id
        if completed_steps is not None:
            values["completed_steps"] = completed_steps

        stmt = update(WorkflowExecutionModel).where(WorkflowExecutionModel.id == id).values(**values)
        await self._session.execute(stmt)

    async def delete(self, id: UUID) -> bool:
        """Delete workflow execution."""
        stmt = select(WorkflowExecutionModel).where(WorkflowExecutionModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            await self._session.delete(model)
            return True
        return False

    def _to_entity(self, model: WorkflowExecutionModel) -> WorkflowExecution:
        """Convert model to entity."""
        return WorkflowExecution(
            execution_id=model.id,
            workflow_definition_id=model.workflow_id,
            tenant_id=model.tenant_id,
            status=model.status,
            current_step_id=model.current_step_id,
            completed_steps=model.completed_steps,
            step_results=model.step_results,
            failed_step_id=model.failed_step_id,
            input_data=model.input_data,
            output_data=model.output_data,
            checkpoint_data=model.checkpoint_data,
            created_at=model.created_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            error=model.error,
        )
