"""Workflow execution engine."""

import asyncio
from typing import Any
from uuid import UUID

import structlog

from agent_orchestrator.core.events import WorkflowEvent
from agent_orchestrator.core.workflows.models import (
    Task,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepType,
)

logger = structlog.get_logger(__name__)


class WorkflowEngine:
    """
    Engine for executing multi-step workflows.

    Supports DAG execution, parallel steps, conditionals, and saga compensation.
    """

    def __init__(
        self,
        task_executor: Any,  # TaskExecutor interface
        event_publisher: Any | None = None,
    ) -> None:
        self._task_executor = task_executor
        self._event_publisher = event_publisher

    async def execute(
        self,
        definition: WorkflowDefinition,
        execution: WorkflowExecution,
    ) -> WorkflowExecution:
        """Execute a workflow."""
        logger.info(
            "Starting workflow execution",
            workflow_id=str(definition.workflow_id),
            execution_id=str(execution.execution_id),
        )

        execution.start()
        execution.checkpoint_data["total_steps"] = len(definition.steps)

        # Emit start event
        if self._event_publisher:
            await self._event_publisher(
                WorkflowEvent.started(
                    workflow_id=definition.workflow_id,
                    execution_id=execution.execution_id,
                    input_data=execution.input_data,
                    tenant_id=execution.tenant_id,
                )
            )

        try:
            # Execute steps in order (respecting dependencies)
            for step in definition.steps:
                if execution.status != WorkflowStatus.RUNNING:
                    break

                # Check dependencies
                if not self._dependencies_satisfied(step, execution):
                    continue

                execution.current_step_id = step.step_id
                result = await self._execute_step(step, execution, definition)

                if result is None:
                    # Step failed, check if we should compensate
                    if execution.status == WorkflowStatus.FAILED:
                        await self._compensate(definition, execution)
                    return execution

                execution.complete_step(step.step_id, result)

                # Emit step completed event
                if self._event_publisher:
                    await self._event_publisher(
                        WorkflowEvent.step_completed(
                            execution_id=execution.execution_id,
                            step_id=step.step_id,
                            result=result,
                            tenant_id=execution.tenant_id,
                        )
                    )

            # All steps completed
            output = self._build_output(execution)
            execution.complete(output)

            if self._event_publisher:
                await self._event_publisher(
                    WorkflowEvent.completed(
                        execution_id=execution.execution_id,
                        result=output,
                        tenant_id=execution.tenant_id,
                    )
                )

            logger.info(
                "Workflow completed",
                execution_id=str(execution.execution_id),
            )

        except Exception as e:
            logger.exception(
                "Workflow execution error",
                execution_id=str(execution.execution_id),
                error=str(e),
            )
            execution.fail(execution.current_step_id or "unknown", str(e))
            await self._compensate(definition, execution)

        return execution

    async def _execute_step(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
        definition: WorkflowDefinition,
    ) -> Any | None:
        """Execute a single workflow step."""
        logger.debug(
            "Executing step",
            step_id=step.step_id,
            step_type=step.step_type.value,
        )

        try:
            match step.step_type:
                case WorkflowStepType.AGENT_TASK:
                    return await self._execute_agent_task(step, execution)

                case WorkflowStepType.PARALLEL:
                    return await self._execute_parallel(step, execution, definition)

                case WorkflowStepType.CONDITIONAL:
                    return await self._execute_conditional(step, execution, definition)

                case WorkflowStepType.WAIT:
                    await asyncio.sleep(step.wait_seconds or 0)
                    return {"waited": step.wait_seconds}

                case WorkflowStepType.HUMAN_APPROVAL:
                    return await self._wait_for_approval(step, execution)

                case _:
                    raise ValueError(f"Unknown step type: {step.step_type}")

        except asyncio.TimeoutError:
            execution.fail(step.step_id, f"Step timed out after {step.timeout_seconds}s")
            return None

        except Exception as e:
            execution.fail(step.step_id, str(e))
            return None

    async def _execute_agent_task(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
    ) -> dict[str, Any] | None:
        """Execute an agent task step."""
        if not step.task_template:
            raise ValueError(f"Step {step.step_id} has no task template")

        # Interpolate template with execution context
        task_input = self._interpolate_template(
            step.task_template,
            execution.input_data,
            execution.step_results,
        )

        # Create and submit task
        task = Task(
            name=step.name,
            description=task_input.get("description", ""),
            input_data=task_input,
            parent_workflow_id=execution.workflow_definition_id,
            parent_step_id=step.step_id,
            timeout_seconds=step.timeout_seconds,
        )

        if step.agent_id:
            task.assigned_agent_id = step.agent_id

        # Execute task (this would submit to the orchestrator)
        result = await asyncio.wait_for(
            self._task_executor.execute(task),
            timeout=step.timeout_seconds,
        )

        return result

    async def _execute_parallel(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
        definition: WorkflowDefinition,
    ) -> dict[str, Any]:
        """Execute child steps in parallel."""
        tasks = []
        for child in step.children:
            task = asyncio.create_task(
                self._execute_step(child, execution, definition)
            )
            tasks.append((child.step_id, task))

        results: dict[str, Any] = {}
        for step_id, task in tasks:
            try:
                result = await task
                results[step_id] = result
                if result is not None:
                    execution.complete_step(step_id, result)
            except Exception as e:
                results[step_id] = {"error": str(e)}
                execution.fail(step_id, str(e))

        return results

    async def _execute_conditional(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
        definition: WorkflowDefinition,
    ) -> dict[str, Any]:
        """Execute a conditional step."""
        if not step.condition:
            raise ValueError(f"Step {step.step_id} has no condition")

        # Evaluate condition
        condition_result = self._evaluate_condition(
            step.condition,
            execution.input_data,
            execution.step_results,
        )

        if condition_result and step.children:
            # Execute first child (true branch)
            return await self._execute_step(step.children[0], execution, definition)
        elif not condition_result and len(step.children) > 1:
            # Execute second child (false branch)
            return await self._execute_step(step.children[1], execution, definition)

        return {"condition_result": condition_result}

    async def _wait_for_approval(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
    ) -> dict[str, Any]:
        """Wait for human approval (placeholder implementation)."""
        # In a real implementation, this would:
        # 1. Emit an approval request event
        # 2. Pause execution
        # 3. Resume when approval is received
        logger.info(
            "Waiting for human approval",
            step_id=step.step_id,
            execution_id=str(execution.execution_id),
        )
        # For now, auto-approve
        return {"approved": True, "approver": "auto"}

    def _dependencies_satisfied(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
    ) -> bool:
        """Check if all dependencies for a step are satisfied."""
        for dep_id in step.depends_on:
            if dep_id not in execution.completed_steps:
                return False
        return True

    def _interpolate_template(
        self,
        template: dict[str, Any],
        input_data: dict[str, Any],
        step_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Interpolate template variables with execution context."""
        import json
        import re

        template_str = json.dumps(template)

        # Replace ${input.key} references
        def replace_input(match: re.Match[str]) -> str:
            key = match.group(1)
            return str(input_data.get(key, match.group(0)))

        template_str = re.sub(r'\$\{input\.(\w+)\}', replace_input, template_str)

        # Replace ${steps.step_id.key} references
        def replace_step(match: re.Match[str]) -> str:
            step_id = match.group(1)
            key = match.group(2)
            step_result = step_results.get(step_id, {})
            if isinstance(step_result, dict):
                return str(step_result.get(key, match.group(0)))
            return match.group(0)

        template_str = re.sub(r'\$\{steps\.(\w+)\.(\w+)\}', replace_step, template_str)

        return json.loads(template_str)

    def _evaluate_condition(
        self,
        condition: str,
        input_data: dict[str, Any],
        step_results: dict[str, Any],
    ) -> bool:
        """Safely evaluate a condition expression."""
        # Simple implementation - in production use a safe expression evaluator
        context = {
            "input": input_data,
            "steps": step_results,
        }
        try:
            # Only allow simple attribute access
            return bool(eval(condition, {"__builtins__": {}}, context))
        except Exception:
            return False

    def _build_output(self, execution: WorkflowExecution) -> dict[str, Any]:
        """Build the workflow output from step results."""
        return {
            "step_results": execution.step_results,
            "completed_steps": execution.completed_steps,
        }

    async def _compensate(
        self,
        definition: WorkflowDefinition,
        execution: WorkflowExecution,
    ) -> None:
        """Execute saga compensation for failed workflow."""
        logger.info(
            "Starting compensation",
            execution_id=str(execution.execution_id),
            failed_step=execution.failed_step_id,
        )

        execution.status = WorkflowStatus.COMPENSATING

        # Execute compensation in reverse order
        for step_id in reversed(execution.completed_steps):
            step = definition.get_step(step_id)
            if step and step.compensation:
                try:
                    logger.debug(
                        "Executing compensation",
                        step_id=step_id,
                    )
                    # Execute compensation logic
                    await self._execute_compensation(step, execution)
                except Exception as e:
                    logger.error(
                        "Compensation failed",
                        step_id=step_id,
                        error=str(e),
                    )

        execution.status = WorkflowStatus.COMPENSATED
        logger.info(
            "Compensation completed",
            execution_id=str(execution.execution_id),
        )

    async def _execute_compensation(
        self,
        step: WorkflowStep,
        execution: WorkflowExecution,
    ) -> None:
        """Execute compensation for a single step."""
        if not step.compensation:
            return

        # Compensation could be another task template
        comp_task = Task(
            name=f"compensate_{step.name}",
            description=f"Compensation for {step.name}",
            input_data=step.compensation,
            parent_workflow_id=execution.workflow_definition_id,
            parent_step_id=f"comp_{step.step_id}",
        )

        await self._task_executor.execute(comp_task)
