"""Unit tests for agent models."""

import pytest

from agent_orchestrator.core.agents import (
    AgentConstraints,
    AgentDefinition,
    AgentInstance,
    AgentStatus,
    MemoryConfig,
    ModelConfig,
    ModelProvider,
)


class TestAgentDefinition:
    """Tests for AgentDefinition model."""

    def test_create_minimal_agent(self) -> None:
        """Test creating an agent with minimal required fields."""
        agent = AgentDefinition(
            name="Test Agent",
            role="Tester",
            goal="Run tests",
        )

        assert agent.name == "Test Agent"
        assert agent.role == "Tester"
        assert agent.goal == "Run tests"
        assert agent.agent_id is not None
        assert agent.llm_config.provider == ModelProvider.ANTHROPIC

    def test_create_full_agent(self) -> None:
        """Test creating an agent with all fields."""
        agent = AgentDefinition(
            name="Full Agent",
            role="Complete Agent",
            goal="Do everything",
            backstory="A fully configured agent",
            llm_config=ModelConfig(
                provider=ModelProvider.OPENAI,
                model_id="gpt-4",
                temperature=0.5,
            ),
            memory=MemoryConfig(
                short_term_max_messages=100,
                long_term_enabled=True,
            ),
            constraints=AgentConstraints(
                max_iterations=50,
                max_tokens_per_task=50000,
            ),
            capabilities={"coding", "testing"},
        )

        assert agent.llm_config.provider == ModelProvider.OPENAI
        assert agent.llm_config.model_id == "gpt-4"
        assert agent.memory.short_term_max_messages == 100
        assert agent.constraints.max_iterations == 50
        assert "coding" in agent.capabilities

    def test_system_prompt_generation(self) -> None:
        """Test system prompt generation."""
        agent = AgentDefinition(
            name="Prompt Agent",
            role="Prompt Generator",
            goal="Generate prompts",
            backstory="An agent specialized in prompts",
        )

        prompt = agent.get_system_prompt()

        assert "Prompt Agent" in prompt
        assert "Prompt Generator" in prompt
        assert "Generate prompts" in prompt
        assert "specialized in prompts" in prompt


class TestAgentInstance:
    """Tests for AgentInstance model."""

    def test_create_instance(self, sample_agent_definition: AgentDefinition) -> None:
        """Test creating an agent instance."""
        instance = AgentInstance(
            agent_definition_id=sample_agent_definition.agent_id,
        )

        assert instance.status == AgentStatus.IDLE
        assert instance.is_available()

    def test_instance_not_available_when_running(
        self, sample_agent_definition: AgentDefinition
    ) -> None:
        """Test that running instances are not available."""
        instance = AgentInstance(
            agent_definition_id=sample_agent_definition.agent_id,
            status=AgentStatus.RUNNING,
        )

        assert not instance.is_available()

    def test_record_task_completion(
        self, sample_agent_definition: AgentDefinition
    ) -> None:
        """Test recording task completion metrics."""
        instance = AgentInstance(
            agent_definition_id=sample_agent_definition.agent_id,
        )

        instance.record_task_completion(
            tokens_used=1000,
            execution_time_ms=5000,
            success=True,
        )

        assert instance.tasks_completed == 1
        assert instance.tasks_failed == 0
        assert instance.total_tokens_used == 1000
        assert instance.total_execution_time_ms == 5000

        instance.record_task_completion(
            tokens_used=500,
            execution_time_ms=2000,
            success=False,
        )

        assert instance.tasks_completed == 1
        assert instance.tasks_failed == 1
        assert instance.total_tokens_used == 1500
