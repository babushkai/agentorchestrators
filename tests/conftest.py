"""Pytest fixtures for agent orchestrator tests."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from agent_orchestrator.api.app import create_app
from agent_orchestrator.config import Settings
from agent_orchestrator.core.agents import AgentDefinition, ModelConfig, ModelProvider
from agent_orchestrator.core.agents.memory import InMemoryStore
from agent_orchestrator.core.agents.tools import ToolRegistry, create_builtin_tools
from agent_orchestrator.core.events.store import InMemoryEventStore
from agent_orchestrator.core.workflows import Task, WorkflowDefinition, WorkflowStep


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        environment="development",
    )


@pytest.fixture
def app(test_settings: Settings) -> Any:
    """Create test FastAPI application."""
    return create_app(test_settings)


@pytest.fixture
def client(app: Any) -> Generator[TestClient, None, None]:
    """Create synchronous test client."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_client(app: Any) -> AsyncGenerator[AsyncClient, None]:
    """Create asynchronous test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def memory_store() -> InMemoryStore:
    """Create in-memory message store."""
    return InMemoryStore()


@pytest.fixture
def event_store() -> InMemoryEventStore:
    """Create in-memory event store."""
    return InMemoryEventStore()


@pytest.fixture
def tool_registry() -> ToolRegistry:
    """Create tool registry with builtin tools."""
    registry = ToolRegistry()
    for tool in create_builtin_tools():
        registry.register(tool)
    return registry


@pytest.fixture
def sample_agent_definition() -> AgentDefinition:
    """Create a sample agent definition."""
    return AgentDefinition(
        name="Test Agent",
        role="Test executor",
        goal="Execute test tasks accurately",
        llm_config=ModelConfig(
            provider=ModelProvider.ANTHROPIC,
            model_id="claude-sonnet-4-20250514",
            temperature=0.7,
        ),
        capabilities={"testing", "general"},
    )


@pytest.fixture
def sample_task() -> Task:
    """Create a sample task."""
    return Task(
        name="Test Task",
        description="A test task for unit testing",
        input_data={"key": "value"},
        required_capabilities={"testing"},
    )


@pytest.fixture
def sample_workflow_definition() -> WorkflowDefinition:
    """Create a sample workflow definition."""
    return WorkflowDefinition(
        name="Test Workflow",
        description="A test workflow",
        steps=[
            WorkflowStep(
                step_id="step1",
                name="First Step",
                task_template={
                    "description": "Process ${input.data}",
                },
            ),
            WorkflowStep(
                step_id="step2",
                name="Second Step",
                depends_on=["step1"],
                task_template={
                    "description": "Continue with ${steps.step1.result}",
                },
            ),
        ],
    )
