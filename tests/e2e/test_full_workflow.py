"""End-to-end tests for full workflow execution."""

import asyncio
from uuid import uuid4

import pytest

from agent_orchestrator.core.agents import AgentDefinition, ModelConfig, ModelProvider
from agent_orchestrator.core.agents.memory import AgentMemory, InMemoryStore
from agent_orchestrator.core.agents.runtime import AgentRuntime, AgentRuntimeFactory
from agent_orchestrator.core.agents.tools import (
    FunctionTool,
    ToolConfig,
    ToolExecutor,
    ToolRegistry,
    create_builtin_tools,
)
from agent_orchestrator.core.orchestration.orchestrator import Orchestrator
from agent_orchestrator.core.workflows import (
    Task,
    TaskPriority,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStep,
    WorkflowStepType,
)
from agent_orchestrator.core.workflows.engine import WorkflowEngine


class MockLLMClient:
    """Mock LLM client for testing without API calls."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = responses or ["I have completed the task."]
        self._call_count = 0

    async def complete(self, **kwargs):
        """Return mock completion."""
        from agent_orchestrator.infrastructure.llm.providers.base import LLMResponse

        response = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1

        return LLMResponse(
            content=response,
            model="mock-model",
            prompt_tokens=100,
            completion_tokens=50,
            finish_reason="stop",
            latency_ms=10.0,
            tool_calls=[],
        )


class MockTaskExecutor:
    """Mock task executor for workflow testing."""

    def __init__(self) -> None:
        self.executed_tasks: list[Task] = []

    async def execute(self, task: Task) -> dict:
        """Execute a mock task."""
        self.executed_tasks.append(task)
        await asyncio.sleep(0.01)  # Simulate some work
        return {"status": "completed", "task_name": task.name}


class TestAgentExecution:
    """Tests for agent task execution."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create tool registry with test tools."""
        registry = ToolRegistry()

        # Add builtin tools
        for tool in create_builtin_tools():
            registry.register(tool)

        # Add a custom test tool
        calc_config = ToolConfig(
            tool_id="test_calculator",
            name="calculator",
            description="Perform basic arithmetic",
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["add", "subtract", "multiply"]},
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["operation", "a", "b"],
            },
        )

        async def calculate(operation: str, a: float, b: float) -> float:
            if operation == "add":
                return a + b
            elif operation == "subtract":
                return a - b
            elif operation == "multiply":
                return a * b
            raise ValueError(f"Unknown operation: {operation}")

        registry.register(FunctionTool(calc_config, calculate))
        return registry

    @pytest.mark.asyncio
    async def test_agent_simple_task(self, tool_registry: ToolRegistry) -> None:
        """Test agent executing a simple task."""
        definition = AgentDefinition(
            name="Test Agent",
            role="Task executor",
            goal="Complete assigned tasks",
            model_config=ModelConfig(
                provider=ModelProvider.ANTHROPIC,
                model_id="mock-model",
            ),
        )

        llm_client = MockLLMClient(["The answer is 42."])
        tool_executor = ToolExecutor(tool_registry)

        runtime = AgentRuntime(
            definition=definition,
            llm_client=llm_client,
            tool_registry=tool_registry,
            tool_executor=tool_executor,
        )

        task_id = uuid4()
        result = await runtime.execute_task(
            task_id=task_id,
            task_input="What is the meaning of life?",
        )

        assert result.success
        assert result.result == "The answer is 42."
        assert result.iterations == 1

    @pytest.mark.asyncio
    async def test_agent_with_memory(self, tool_registry: ToolRegistry) -> None:
        """Test agent with memory persistence."""
        definition = AgentDefinition(
            name="Memory Agent",
            role="Remembering assistant",
            goal="Remember context across interactions",
        )

        memory_store = InMemoryStore()
        memory = AgentMemory(definition.agent_id, memory_store)

        llm_client = MockLLMClient(["I remember our conversation."])
        tool_executor = ToolExecutor(tool_registry)

        runtime = AgentRuntime(
            definition=definition,
            llm_client=llm_client,
            tool_registry=tool_registry,
            tool_executor=tool_executor,
            memory=memory,
        )

        task_id = uuid4()
        result = await runtime.execute_task(
            task_id=task_id,
            task_input="Remember this: the secret code is 12345",
        )

        assert result.success

        # Check memory was stored
        memory.set_task(task_id)
        messages = await memory.get_context()
        assert len(messages) >= 1


class TestOrchestratorRouting:
    """Tests for orchestrator task routing."""

    @pytest.mark.asyncio
    async def test_task_submission_and_routing(self) -> None:
        """Test submitting and routing tasks."""
        orchestrator = Orchestrator()
        await orchestrator.start()

        try:
            # Register an agent
            definition = AgentDefinition(
                name="Router Test Agent",
                role="Test agent",
                goal="Handle routed tasks",
                capabilities={"testing"},
            )

            instance = await orchestrator.register_agent(definition)
            assert instance.is_available()

            # Submit a task
            task = Task(
                name="Routed Task",
                description="A task to be routed",
                required_capabilities={"testing"},
                priority=TaskPriority.NORMAL,
            )

            await orchestrator.submit_task(task)

            # Give dispatcher time to route
            await asyncio.sleep(0.2)

            # Check metrics
            metrics = orchestrator.get_metrics()
            assert metrics["total_agents"] == 1

        finally:
            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_priority_queue_ordering(self) -> None:
        """Test that high priority tasks are processed first."""
        orchestrator = Orchestrator()

        # Submit tasks with different priorities
        low_task = Task(
            name="Low Priority",
            description="Low priority task",
            priority=TaskPriority.LOW,
        )
        high_task = Task(
            name="High Priority",
            description="High priority task",
            priority=TaskPriority.HIGH,
        )
        critical_task = Task(
            name="Critical Priority",
            description="Critical priority task",
            priority=TaskPriority.CRITICAL,
        )

        await orchestrator.submit_task(low_task)
        await orchestrator.submit_task(high_task)
        await orchestrator.submit_task(critical_task)

        # First task should be critical
        first = await orchestrator._task_queue.get()
        assert first.priority == TaskPriority.CRITICAL

        second = await orchestrator._task_queue.get()
        assert second.priority == TaskPriority.HIGH


class TestWorkflowExecution:
    """Tests for workflow engine execution."""

    @pytest.fixture
    def task_executor(self) -> MockTaskExecutor:
        return MockTaskExecutor()

    @pytest.fixture
    def workflow_engine(self, task_executor: MockTaskExecutor) -> WorkflowEngine:
        return WorkflowEngine(task_executor=task_executor)

    @pytest.mark.asyncio
    async def test_sequential_workflow(
        self,
        workflow_engine: WorkflowEngine,
        task_executor: MockTaskExecutor,
    ) -> None:
        """Test executing a sequential workflow."""
        definition = WorkflowDefinition(
            name="Sequential Workflow",
            description="A simple sequential workflow",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    name="First Step",
                    step_type=WorkflowStepType.AGENT_TASK,
                    task_template={"description": "Do step 1"},
                ),
                WorkflowStep(
                    step_id="step2",
                    name="Second Step",
                    step_type=WorkflowStepType.AGENT_TASK,
                    depends_on=["step1"],
                    task_template={"description": "Do step 2"},
                ),
            ],
        )

        execution = WorkflowExecution(
            workflow_definition_id=definition.workflow_id,
            input_data={"initial": "data"},
        )

        result = await workflow_engine.execute(definition, execution)

        assert result.status.value == "completed"
        assert len(result.completed_steps) == 2
        assert "step1" in result.completed_steps
        assert "step2" in result.completed_steps

    @pytest.mark.asyncio
    async def test_parallel_workflow(
        self,
        workflow_engine: WorkflowEngine,
        task_executor: MockTaskExecutor,
    ) -> None:
        """Test executing parallel steps."""
        definition = WorkflowDefinition(
            name="Parallel Workflow",
            steps=[
                WorkflowStep(
                    step_id="parallel_group",
                    name="Parallel Steps",
                    step_type=WorkflowStepType.PARALLEL,
                    children=[
                        WorkflowStep(
                            step_id="parallel_a",
                            name="Parallel A",
                            step_type=WorkflowStepType.AGENT_TASK,
                            task_template={"description": "Parallel task A"},
                        ),
                        WorkflowStep(
                            step_id="parallel_b",
                            name="Parallel B",
                            step_type=WorkflowStepType.AGENT_TASK,
                            task_template={"description": "Parallel task B"},
                        ),
                    ],
                ),
            ],
        )

        execution = WorkflowExecution(
            workflow_definition_id=definition.workflow_id,
        )

        result = await workflow_engine.execute(definition, execution)

        assert result.status.value == "completed"
        assert "parallel_group" in result.completed_steps

    @pytest.mark.asyncio
    async def test_workflow_with_wait_step(
        self,
        workflow_engine: WorkflowEngine,
    ) -> None:
        """Test workflow with wait step."""
        definition = WorkflowDefinition(
            name="Wait Workflow",
            steps=[
                WorkflowStep(
                    step_id="wait_step",
                    name="Wait",
                    step_type=WorkflowStepType.WAIT,
                    wait_seconds=1,
                ),
            ],
        )

        execution = WorkflowExecution(
            workflow_definition_id=definition.workflow_id,
        )

        result = await workflow_engine.execute(definition, execution)

        assert result.status.value == "completed"
        assert "wait_step" in result.completed_steps


class TestFullE2EFlow:
    """Full end-to-end flow tests."""

    @pytest.mark.asyncio
    async def test_complete_agent_workflow_cycle(self) -> None:
        """Test a complete cycle: submit task -> route -> execute -> complete."""
        # This test simulates the full flow without external dependencies

        events_published: list = []

        async def mock_event_handler(event):
            events_published.append(event)

        # Create orchestrator
        orchestrator = Orchestrator(event_publisher=mock_event_handler)
        await orchestrator.start()

        try:
            # Register agent
            definition = AgentDefinition(
                name="E2E Agent",
                role="End-to-end test agent",
                goal="Complete e2e test",
                capabilities={"e2e_testing"},
            )
            instance = await orchestrator.register_agent(definition)

            # Submit task
            task = Task(
                name="E2E Task",
                description="End-to-end test task",
                required_capabilities={"e2e_testing"},
            )
            await orchestrator.submit_task(task)

            # Wait for assignment
            await asyncio.sleep(0.2)

            # Simulate task completion
            await orchestrator.complete_task(
                task.task_id,
                {"result": "E2E test completed successfully"},
            )

            # Verify events were published
            event_types = [e.event_type.value for e in events_published]
            assert "task.created" in event_types
            assert "task.completed" in event_types

        finally:
            await orchestrator.stop()
