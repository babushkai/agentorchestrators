"""Saga pattern implementation for distributed transactions."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class SagaStepStatus(str, Enum):
    """Status of a saga step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


@dataclass
class SagaStepResult:
    """Result of a saga step execution."""

    success: bool
    data: Any = None
    error: str | None = None


class SagaStep(ABC, Generic[T]):
    """Abstract base class for saga steps."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.step_id = str(uuid4())

    @abstractmethod
    async def execute(self, context: T) -> SagaStepResult:
        """Execute the step's action."""
        ...

    @abstractmethod
    async def compensate(self, context: T) -> SagaStepResult:
        """Execute the step's compensation (rollback)."""
        ...


@dataclass
class SagaExecutionState:
    """State of a saga execution."""

    saga_id: UUID = field(default_factory=uuid4)
    status: str = "pending"
    current_step: int = 0
    completed_steps: list[str] = field(default_factory=list)
    step_results: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class Saga(Generic[T]):
    """
    Saga orchestrator for distributed transactions.

    Implements the orchestration-based saga pattern where a central coordinator
    manages the execution of steps and compensations.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.saga_id = uuid4()
        self._steps: list[SagaStep[T]] = []

    def add_step(self, step: SagaStep[T]) -> "Saga[T]":
        """Add a step to the saga."""
        self._steps.append(step)
        return self

    async def execute(self, context: T) -> SagaExecutionState:
        """
        Execute the saga.

        Runs all steps in order. If any step fails, compensates
        all previously completed steps in reverse order.
        """
        state = SagaExecutionState(saga_id=self.saga_id)
        state.status = "running"
        state.started_at = datetime.now(timezone.utc)

        logger.info(
            "Starting saga execution",
            saga_id=str(self.saga_id),
            saga_name=self.name,
            step_count=len(self._steps),
        )

        try:
            # Execute steps forward
            for i, step in enumerate(self._steps):
                state.current_step = i

                logger.debug(
                    "Executing saga step",
                    saga_id=str(self.saga_id),
                    step_name=step.name,
                    step_index=i,
                )

                result = await step.execute(context)

                if result.success:
                    state.completed_steps.append(step.step_id)
                    state.step_results[step.step_id] = result.data
                else:
                    # Step failed, start compensation
                    state.error = result.error
                    logger.warning(
                        "Saga step failed, starting compensation",
                        saga_id=str(self.saga_id),
                        step_name=step.name,
                        error=result.error,
                    )
                    await self._compensate(context, state)
                    state.status = "compensated"
                    state.completed_at = datetime.now(timezone.utc)
                    return state

            # All steps completed successfully
            state.status = "completed"
            state.completed_at = datetime.now(timezone.utc)

            logger.info(
                "Saga completed successfully",
                saga_id=str(self.saga_id),
                saga_name=self.name,
            )

        except Exception as e:
            state.error = str(e)
            logger.exception(
                "Saga execution error",
                saga_id=str(self.saga_id),
                error=str(e),
            )
            await self._compensate(context, state)
            state.status = "compensated"
            state.completed_at = datetime.now(timezone.utc)

        return state

    async def _compensate(self, context: T, state: SagaExecutionState) -> None:
        """Compensate all completed steps in reverse order."""
        state.status = "compensating"

        logger.info(
            "Starting saga compensation",
            saga_id=str(self.saga_id),
            completed_steps=len(state.completed_steps),
        )

        # Get steps to compensate in reverse order
        steps_to_compensate = []
        for step in self._steps:
            if step.step_id in state.completed_steps:
                steps_to_compensate.append(step)

        for step in reversed(steps_to_compensate):
            try:
                logger.debug(
                    "Compensating saga step",
                    saga_id=str(self.saga_id),
                    step_name=step.name,
                )
                await step.compensate(context)
            except Exception as e:
                # Log but continue with other compensations
                logger.error(
                    "Compensation failed",
                    saga_id=str(self.saga_id),
                    step_name=step.name,
                    error=str(e),
                )


class FunctionSagaStep(SagaStep[T]):
    """Saga step backed by async functions."""

    def __init__(
        self,
        name: str,
        execute_fn: Any,
        compensate_fn: Any,
    ) -> None:
        super().__init__(name)
        self._execute_fn = execute_fn
        self._compensate_fn = compensate_fn

    async def execute(self, context: T) -> SagaStepResult:
        try:
            result = await self._execute_fn(context)
            return SagaStepResult(success=True, data=result)
        except Exception as e:
            return SagaStepResult(success=False, error=str(e))

    async def compensate(self, context: T) -> SagaStepResult:
        try:
            result = await self._compensate_fn(context)
            return SagaStepResult(success=True, data=result)
        except Exception as e:
            return SagaStepResult(success=False, error=str(e))


class SagaBuilder(Generic[T]):
    """Fluent builder for creating sagas."""

    def __init__(self, name: str) -> None:
        self._saga = Saga[T](name)

    def step(
        self,
        name: str,
        execute: Any,
        compensate: Any,
    ) -> "SagaBuilder[T]":
        """Add a step with execute and compensate functions."""
        step = FunctionSagaStep[T](name, execute, compensate)
        self._saga.add_step(step)
        return self

    def build(self) -> Saga[T]:
        """Build the saga."""
        return self._saga


# Example usage helpers
@dataclass
class WorkflowSagaContext:
    """Context for workflow saga execution."""

    workflow_id: UUID
    execution_id: UUID
    input_data: dict[str, Any]
    step_results: dict[str, Any] = field(default_factory=dict)
    resources_allocated: list[str] = field(default_factory=list)


async def create_workflow_saga() -> Saga[WorkflowSagaContext]:
    """Create a saga for multi-agent workflow execution."""

    async def allocate_resources(ctx: WorkflowSagaContext) -> dict:
        # Allocate compute resources for agents
        ctx.resources_allocated.append("compute-pool-1")
        return {"allocated": True}

    async def deallocate_resources(ctx: WorkflowSagaContext) -> dict:
        # Release allocated resources
        ctx.resources_allocated.clear()
        return {"deallocated": True}

    async def start_agents(ctx: WorkflowSagaContext) -> dict:
        # Start required agents
        return {"agents_started": True}

    async def stop_agents(ctx: WorkflowSagaContext) -> dict:
        # Stop agents
        return {"agents_stopped": True}

    async def execute_workflow(ctx: WorkflowSagaContext) -> dict:
        # Execute workflow steps
        ctx.step_results["workflow"] = "completed"
        return {"result": ctx.step_results}

    async def rollback_workflow(ctx: WorkflowSagaContext) -> dict:
        # Rollback workflow changes
        return {"rolled_back": True}

    saga = (
        SagaBuilder[WorkflowSagaContext]("multi-agent-workflow")
        .step("allocate-resources", allocate_resources, deallocate_resources)
        .step("start-agents", start_agents, stop_agents)
        .step("execute-workflow", execute_workflow, rollback_workflow)
        .build()
    )

    return saga
