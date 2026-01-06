"""Unit tests for workflow models."""

import pytest
from uuid import uuid4

from agent_orchestrator.core.workflows import (
    Task,
    TaskPriority,
    TaskStatus,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepType,
)


class TestTask:
    """Tests for Task model."""

    def test_create_task(self) -> None:
        """Test creating a task with defaults."""
        task = Task(
            name="Test Task",
            description="A test task",
        )

        assert task.name == "Test Task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.NORMAL
        assert task.task_id is not None

    def test_task_start(self) -> None:
        """Test starting a task."""
        task = Task(name="Test", description="Test")
        agent_id = uuid4()

        task.start(agent_id)

        assert task.status == TaskStatus.RUNNING
        assert task.assigned_agent_id == agent_id
        assert task.started_at is not None

    def test_task_complete(self) -> None:
        """Test completing a task."""
        task = Task(name="Test", description="Test")
        result = {"output": "success"}

        task.complete(result)

        assert task.status == TaskStatus.COMPLETED
        assert task.result == result
        assert task.completed_at is not None

    def test_task_fail(self) -> None:
        """Test failing a task."""
        task = Task(name="Test", description="Test")

        task.fail("Something went wrong")

        assert task.status == TaskStatus.FAILED
        assert task.error == "Something went wrong"

    def test_task_retry(self) -> None:
        """Test task retry logic."""
        task = Task(name="Test", description="Test", max_retries=3)

        assert task.can_retry()

        task.retry_count = 3
        assert not task.can_retry()


class TestWorkflowDefinition:
    """Tests for WorkflowDefinition model."""

    def test_create_workflow(self) -> None:
        """Test creating a workflow definition."""
        workflow = WorkflowDefinition(
            name="Test Workflow",
            description="A test workflow",
            steps=[
                WorkflowStep(step_id="step1", name="Step 1"),
                WorkflowStep(step_id="step2", name="Step 2"),
            ],
        )

        assert workflow.name == "Test Workflow"
        assert len(workflow.steps) == 2
        assert workflow.version == "1.0.0"

    def test_get_step(self) -> None:
        """Test finding a step by ID."""
        workflow = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(step_id="step1", name="Step 1"),
                WorkflowStep(
                    step_id="parent",
                    name="Parent",
                    step_type=WorkflowStepType.PARALLEL,
                    children=[
                        WorkflowStep(step_id="child1", name="Child 1"),
                    ],
                ),
            ],
        )

        assert workflow.get_step("step1") is not None
        assert workflow.get_step("child1") is not None
        assert workflow.get_step("nonexistent") is None


class TestWorkflowExecution:
    """Tests for WorkflowExecution model."""

    def test_create_execution(self) -> None:
        """Test creating a workflow execution."""
        execution = WorkflowExecution(
            workflow_definition_id=uuid4(),
            input_data={"key": "value"},
        )

        assert execution.status == WorkflowStatus.PENDING
        assert execution.input_data == {"key": "value"}

    def test_execution_start(self) -> None:
        """Test starting an execution."""
        execution = WorkflowExecution(workflow_definition_id=uuid4())

        execution.start()

        assert execution.status == WorkflowStatus.RUNNING
        assert execution.started_at is not None

    def test_complete_step(self) -> None:
        """Test completing a step."""
        execution = WorkflowExecution(workflow_definition_id=uuid4())
        execution.checkpoint_data = {"total_steps": 3}

        execution.complete_step("step1", {"result": "done"})

        assert "step1" in execution.completed_steps
        assert execution.step_results["step1"] == {"result": "done"}

    def test_execution_progress(self) -> None:
        """Test progress calculation."""
        execution = WorkflowExecution(workflow_definition_id=uuid4())
        execution.checkpoint_data = {"total_steps": 4}

        assert execution.progress_percentage == 0.0

        execution.completed_steps = ["step1", "step2"]
        assert execution.progress_percentage == 50.0

    def test_execution_fail(self) -> None:
        """Test failing an execution."""
        execution = WorkflowExecution(workflow_definition_id=uuid4())

        execution.fail("step2", "Step failed")

        assert execution.status == WorkflowStatus.FAILED
        assert execution.failed_step_id == "step2"
        assert execution.error == "Step failed"

    def test_execution_complete(self) -> None:
        """Test completing an execution."""
        execution = WorkflowExecution(workflow_definition_id=uuid4())
        output = {"final": "result"}

        execution.complete(output)

        assert execution.status == WorkflowStatus.COMPLETED
        assert execution.output_data == output
        assert execution.completed_at is not None
