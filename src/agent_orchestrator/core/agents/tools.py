"""Tool registry and execution framework."""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

from agent_orchestrator.core.agents.definition import ToolConfig

if TYPE_CHECKING:
    from agent_orchestrator.infrastructure.storage.object_store import ObjectStore

logger = structlog.get_logger(__name__)


class BuiltinToolCategory(str, Enum):
    """Categories of built-in tools."""

    REASONING = "reasoning"  # think, final_answer
    CALCULATOR = "calculator"  # Mathematical calculations
    HTTP = "http"  # HTTP requests
    FILE = "file"  # File operations
    SCRAPING = "scraping"  # Web scraping
    CODE = "code"  # Code execution


class ToolCall(BaseModel):
    """Represents a tool call request from an agent."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    arguments: dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ToolResult(BaseModel):
    """Result of a tool execution."""

    tool_call_id: str
    name: str
    success: bool
    result: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0


class Tool(ABC):
    """Abstract base class for tools."""

    def __init__(self, config: ToolConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def description(self) -> str:
        return self.config.description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return self.config.parameters_schema

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with the given arguments."""
        ...

    def to_llm_schema(self) -> dict[str, Any]:
        """Convert to LLM tool schema format (OpenAI/Anthropic compatible)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


class FunctionTool(Tool):
    """Tool backed by a Python function."""

    def __init__(
        self,
        config: ToolConfig,
        func: Callable[..., Any] | Callable[..., Awaitable[Any]],
    ) -> None:
        super().__init__(config)
        self._func = func
        self._is_async = asyncio.iscoroutinefunction(func)

    async def execute(self, **kwargs: Any) -> Any:
        if self._is_async:
            return await self._func(**kwargs)
        else:
            # Run sync functions in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: self._func(**kwargs))


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.debug("Tool registered", tool_name=tool.name)

    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_llm_schemas(self, allowed: list[str] | None = None) -> list[dict[str, Any]]:
        """Get tool schemas for LLM API calls."""
        tools = self._tools.values()
        if allowed:
            tools = [t for t in tools if t.name in allowed]
        return [t.to_llm_schema() for t in tools]


class ToolExecutor:
    """Executes tool calls with timeout and error handling."""

    def __init__(
        self,
        registry: ToolRegistry,
        default_timeout: float = 30.0,
        max_retries: int = 0,
    ) -> None:
        self._registry = registry
        self._default_timeout = default_timeout
        self._max_retries = max_retries

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call."""
        start_time = datetime.now(timezone.utc)

        tool = self._registry.get(tool_call.name)
        if not tool:
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                success=False,
                error=f"Tool '{tool_call.name}' not found",
            )

        timeout = tool.config.timeout_seconds or self._default_timeout
        retries = 0
        last_error: str | None = None

        while retries <= (tool.config.retry_count or self._max_retries):
            try:
                result = await asyncio.wait_for(
                    tool.execute(**tool_call.arguments),
                    timeout=timeout,
                )

                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

                return ToolResult(
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    success=True,
                    result=result,
                    execution_time_ms=execution_time,
                )

            except asyncio.TimeoutError:
                last_error = f"Tool execution timed out after {timeout}s"
                logger.warning(
                    "Tool execution timeout",
                    tool_name=tool_call.name,
                    timeout=timeout,
                    retry=retries,
                )
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Tool execution failed",
                    tool_name=tool_call.name,
                    error=last_error,
                    retry=retries,
                )

            retries += 1
            if retries <= (tool.config.retry_count or self._max_retries):
                await asyncio.sleep(tool.config.retry_delay_seconds)

        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        return ToolResult(
            tool_call_id=tool_call.id,
            name=tool_call.name,
            success=False,
            error=last_error,
            execution_time_ms=execution_time,
        )

    async def execute_batch(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute multiple tool calls concurrently."""
        tasks = [self.execute(call) for call in tool_calls]
        return await asyncio.gather(*tasks)


# Built-in tools
def create_builtin_tools(
    categories: list[BuiltinToolCategory] | None = None,
    object_store: "ObjectStore | None" = None,
    task_id: UUID | None = None,
) -> list[Tool]:
    """Create built-in utility tools.

    Args:
        categories: List of tool categories to include. None means all categories.
        object_store: Object store for file operations (required for FILE category).
        task_id: Task ID for file operations namespace (required for FILE category).

    Returns:
        List of configured tools.
    """
    tools: list[Tool] = []
    include_all = categories is None

    # Reasoning tools (think, final_answer) - always included by default
    if include_all or BuiltinToolCategory.REASONING in categories:
        # Think tool - for step-by-step reasoning
        think_config = ToolConfig(
            tool_id="builtin_think",
            name="think",
            description="Use this tool to think through a problem step by step before taking action.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "thought": {
                        "type": "string",
                        "description": "Your reasoning or thought process",
                    }
                },
                "required": ["thought"],
            },
        )

        async def think_func(thought: str) -> str:
            return f"Thought recorded: {thought}"

        tools.append(FunctionTool(think_config, think_func))

        # Final answer tool
        answer_config = ToolConfig(
            tool_id="builtin_final_answer",
            name="final_answer",
            description="Use this tool to provide your final answer to the user's request.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "Your final answer",
                    }
                },
                "required": ["answer"],
            },
        )

        async def answer_func(answer: str) -> str:
            return answer

        tools.append(FunctionTool(answer_config, answer_func))

    # Calculator tool
    if include_all or BuiltinToolCategory.CALCULATOR in categories:
        from agent_orchestrator.core.agents.builtin_tools.calculator import CalculatorTool

        tools.append(CalculatorTool())

    # HTTP request tool
    if include_all or BuiltinToolCategory.HTTP in categories:
        from agent_orchestrator.core.agents.builtin_tools.http_tool import HTTPTool

        tools.append(HTTPTool())

    # File operations tool (requires object_store and task_id)
    if include_all or BuiltinToolCategory.FILE in categories:
        if object_store is not None and task_id is not None:
            from agent_orchestrator.core.agents.builtin_tools.file_tool import FileOperationsTool

            tools.append(FileOperationsTool(object_store, task_id))
        else:
            logger.debug(
                "FILE tools not created: object_store or task_id not provided",
                has_object_store=object_store is not None,
                has_task_id=task_id is not None,
            )

    # Web scraping tool
    if include_all or BuiltinToolCategory.SCRAPING in categories:
        from agent_orchestrator.core.agents.builtin_tools.scraper import WebScrapingTool

        tools.append(WebScrapingTool())

    # Code execution tool
    if include_all or BuiltinToolCategory.CODE in categories:
        from agent_orchestrator.core.agents.builtin_tools.code_exec import CodeExecutionTool

        tools.append(CodeExecutionTool())

    return tools
