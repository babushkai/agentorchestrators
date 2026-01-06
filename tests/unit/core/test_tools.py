"""Unit tests for tool system."""

import pytest

from agent_orchestrator.core.agents.tools import (
    FunctionTool,
    ToolCall,
    ToolConfig,
    ToolExecutor,
    ToolRegistry,
    create_builtin_tools,
)


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_tool(self) -> None:
        """Test registering a tool."""
        registry = ToolRegistry()

        config = ToolConfig(
            tool_id="test",
            name="test_tool",
            description="A test tool",
            parameters_schema={"type": "object", "properties": {}},
        )

        async def test_func() -> str:
            return "test"

        tool = FunctionTool(config, test_func)
        registry.register(tool)

        assert registry.get("test_tool") is not None
        assert len(registry.list_tools()) == 1

    def test_unregister_tool(self) -> None:
        """Test unregistering a tool."""
        registry = ToolRegistry()

        config = ToolConfig(
            tool_id="test",
            name="test_tool",
            description="A test tool",
            parameters_schema={},
        )

        async def test_func() -> str:
            return "test"

        tool = FunctionTool(config, test_func)
        registry.register(tool)
        registry.unregister("test_tool")

        assert registry.get("test_tool") is None

    def test_get_llm_schemas(self) -> None:
        """Test getting LLM-compatible schemas."""
        registry = ToolRegistry()
        for tool in create_builtin_tools():
            registry.register(tool)

        schemas = registry.get_llm_schemas()

        assert len(schemas) > 0
        for schema in schemas:
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]


class TestToolExecutor:
    """Tests for ToolExecutor."""

    @pytest.fixture
    def registry(self) -> ToolRegistry:
        """Create a registry with test tools."""
        registry = ToolRegistry()

        config = ToolConfig(
            tool_id="add",
            name="add",
            description="Add two numbers",
            parameters_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        )

        async def add_func(a: float, b: float) -> float:
            return a + b

        registry.register(FunctionTool(config, add_func))
        return registry

    @pytest.mark.asyncio
    async def test_execute_tool(self, registry: ToolRegistry) -> None:
        """Test executing a tool."""
        executor = ToolExecutor(registry)

        call = ToolCall(name="add", arguments={"a": 2, "b": 3})
        result = await executor.execute(call)

        assert result.success
        assert result.result == 5.0

    @pytest.mark.asyncio
    async def test_execute_missing_tool(self, registry: ToolRegistry) -> None:
        """Test executing a missing tool."""
        executor = ToolExecutor(registry)

        call = ToolCall(name="nonexistent", arguments={})
        result = await executor.execute(call)

        assert not result.success
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_batch(self, registry: ToolRegistry) -> None:
        """Test executing multiple tools."""
        executor = ToolExecutor(registry)

        calls = [
            ToolCall(name="add", arguments={"a": 1, "b": 2}),
            ToolCall(name="add", arguments={"a": 3, "b": 4}),
        ]

        results = await executor.execute_batch(calls)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].result == 3.0
        assert results[1].result == 7.0


class TestBuiltinTools:
    """Tests for builtin tools."""

    def test_builtin_tools_exist(self) -> None:
        """Test that builtin tools are created."""
        tools = create_builtin_tools()

        assert len(tools) >= 2

        tool_names = [t.name for t in tools]
        assert "think" in tool_names
        assert "final_answer" in tool_names

    @pytest.mark.asyncio
    async def test_think_tool(self) -> None:
        """Test the think tool."""
        tools = create_builtin_tools()
        think_tool = next(t for t in tools if t.name == "think")

        result = await think_tool.execute(thought="I need to analyze this carefully")

        assert "Thought recorded" in result

    @pytest.mark.asyncio
    async def test_final_answer_tool(self) -> None:
        """Test the final answer tool."""
        tools = create_builtin_tools()
        answer_tool = next(t for t in tools if t.name == "final_answer")

        result = await answer_tool.execute(answer="The answer is 42")

        assert result == "The answer is 42"
