"""Agent runtime execution engine."""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog

from agent_orchestrator.core.agents.definition import AgentDefinition, AgentStatus
from agent_orchestrator.core.agents.memory import AgentMemory, InMemoryStore, Message
from agent_orchestrator.core.agents.tools import ToolCall, ToolExecutor, ToolRegistry, ToolResult
from agent_orchestrator.core.events import AgentEvent
from agent_orchestrator.infrastructure.llm import LLMClient, LLMMessage, LLMResponse

logger = structlog.get_logger(__name__)


def _parse_text_tool_call(content: str, available_tools: list[str]) -> dict[str, Any] | None:
    """
    Attempt to parse a tool call from text content.
    
    Some local models output tool calls as JSON text instead of structured tool calls.
    This function tries to extract and parse such calls.
    
    Returns a dict with 'name' and 'arguments' if found, None otherwise.
    """
    if not content:
        return None
    
    content = content.strip()
    
    # Try to find JSON object in content
    # Look for patterns like {"name": "tool_name", "parameters": {...}}
    json_patterns = [
        r'\{[^{}]*"name"\s*:\s*"([^"]+)"[^{}]*\}',  # Simple JSON with name
        r'```json\s*(\{.*?\})\s*```',  # JSON in code block
        r'```\s*(\{.*?\})\s*```',  # JSON in generic code block
    ]
    
    for pattern in json_patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                # Try to parse the full JSON if we captured it
                if match.lastindex and match.lastindex >= 1:
                    json_str = match.group(1) if '{' in match.group(1) else match.group(0)
                else:
                    json_str = match.group(0)
                
                # Clean up the JSON string
                json_str = json_str.strip()
                if not json_str.startswith('{'):
                    continue
                    
                data = json.loads(json_str)
                
                # Check if it looks like a tool call
                if isinstance(data, dict) and "name" in data:
                    tool_name = data.get("name")
                    if tool_name in available_tools:
                        # Extract arguments/parameters
                        arguments = data.get("parameters") or data.get("arguments") or {}
                        return {"name": tool_name, "arguments": arguments}
            except (json.JSONDecodeError, AttributeError):
                continue
    
    # Try direct JSON parse if content looks like JSON
    if content.startswith('{') and content.endswith('}'):
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "name" in data:
                tool_name = data.get("name")
                if tool_name in available_tools:
                    arguments = data.get("parameters") or data.get("arguments") or {}
                    return {"name": tool_name, "arguments": arguments}
        except json.JSONDecodeError:
            pass
    
    return None


class AgentExecutionResult:
    """Result of agent task execution."""

    def __init__(
        self,
        success: bool,
        result: Any = None,
        error: str | None = None,
        iterations: int = 0,
        total_tokens: int = 0,
        execution_time_ms: float = 0.0,
    ) -> None:
        self.success = success
        self.result = result
        self.error = error
        self.iterations = iterations
        self.total_tokens = total_tokens
        self.execution_time_ms = execution_time_ms


class AgentRuntime:
    """
    Agent runtime execution engine.

    Implements the observe-think-act loop for autonomous agent execution.
    """

    def __init__(
        self,
        definition: AgentDefinition,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
        memory: AgentMemory | None = None,
        event_handler: Any | None = None,
    ) -> None:
        self._definition = definition
        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._tool_executor = tool_executor
        self._memory = memory or AgentMemory(
            definition.agent_id,
            InMemoryStore(),
            definition.memory.short_term_max_messages,
        )
        self._event_handler = event_handler
        self._status = AgentStatus.IDLE
        self._current_task_id: UUID | None = None

    @property
    def status(self) -> AgentStatus:
        return self._status

    @property
    def agent_id(self) -> UUID:
        return self._definition.agent_id

    async def execute_task(
        self,
        task_id: UUID,
        task_input: str,
        context: dict[str, Any] | None = None,
    ) -> AgentExecutionResult:
        """Execute a task using the observe-think-act loop."""
        self._status = AgentStatus.RUNNING
        self._current_task_id = task_id
        self._memory.set_task(task_id)

        start_time = datetime.now(timezone.utc)
        total_tokens = 0
        iterations = 0

        try:
            # Initialize conversation with system prompt and task
            system_prompt = self._definition.get_system_prompt()
            await self._memory.add_user_message(task_input)

            # Get available tools
            allowed_tools = self._definition.constraints.allowed_tools
            tool_schemas = self._tool_registry.get_llm_schemas(allowed_tools)

            # Main execution loop
            while iterations < self._definition.constraints.max_iterations:
                iterations += 1

                logger.debug(
                    "Agent iteration",
                    agent_id=str(self.agent_id),
                    task_id=str(task_id),
                    iteration=iterations,
                )

                # Build messages for LLM
                messages = await self._build_messages(system_prompt)

                # Get LLM response
                response = await self._llm_client.complete(
                    messages=messages,
                    provider=self._definition.llm_config.provider,
                    model=self._definition.llm_config.model_id,
                    temperature=self._definition.llm_config.temperature,
                    max_tokens=self._definition.llm_config.max_tokens,
                    tools=tool_schemas if tool_schemas else None,
                    tool_choice="auto" if tool_schemas else None,
                )

                total_tokens += response.prompt_tokens + response.completion_tokens

                # Emit LLM call event
                if self._event_handler:
                    await self._event_handler(
                        AgentEvent.llm_call(
                            agent_id=self.agent_id,
                            task_id=task_id,
                            model=response.model,
                            prompt_tokens=response.prompt_tokens,
                            completion_tokens=response.completion_tokens,
                            latency_ms=response.latency_ms,
                        )
                    )

                # Check for token limit
                if total_tokens >= self._definition.constraints.max_tokens_per_task:
                    raise RuntimeError(
                        f"Token limit exceeded: {total_tokens} >= "
                        f"{self._definition.constraints.max_tokens_per_task}"
                    )

                # Process response
                if response.has_tool_calls:
                    # Execute tool calls
                    result = await self._handle_tool_calls(response, task_id)
                    if result is not None:
                        # Agent signaled completion via final_answer tool
                        execution_time = (
                            datetime.now(timezone.utc) - start_time
                        ).total_seconds() * 1000
                        self._status = AgentStatus.IDLE
                        return AgentExecutionResult(
                            success=True,
                            result=result,
                            iterations=iterations,
                            total_tokens=total_tokens,
                            execution_time_ms=execution_time,
                        )
                else:
                    # No structured tool calls - check if the content contains a text-based tool call
                    # (some local models output tool calls as JSON text)
                    text_tool_call = _parse_text_tool_call(
                        response.content or "", 
                        allowed_tools or []
                    )
                    
                    if text_tool_call:
                        # Found a text-based tool call, execute it
                        logger.debug(
                            "Parsed text-based tool call",
                            tool_name=text_tool_call["name"],
                            agent_id=str(self.agent_id),
                        )
                        
                        # Create a synthetic tool call and execute
                        tool_call = ToolCall(
                            id=str(uuid4()),
                            name=text_tool_call["name"],
                            arguments=text_tool_call["arguments"],
                        )
                        
                        # Check for final_answer
                        if tool_call.name == "final_answer":
                            execution_time = (
                                datetime.now(timezone.utc) - start_time
                            ).total_seconds() * 1000
                            self._status = AgentStatus.IDLE
                            return AgentExecutionResult(
                                success=True,
                                result=tool_call.arguments.get("answer"),
                                iterations=iterations,
                                total_tokens=total_tokens,
                                execution_time_ms=execution_time,
                            )
                        
                        # Execute the tool
                        result = await self._tool_executor.execute(tool_call)
                        
                        # Emit tool call event
                        if self._event_handler:
                            await self._event_handler(
                                AgentEvent.tool_call(
                                    agent_id=self.agent_id,
                                    task_id=task_id,
                                    tool_name=tool_call.name,
                                    success=result.success,
                                    execution_time_ms=result.execution_time_ms,
                                )
                            )
                        
                        # Store assistant message with the text tool call
                        await self._memory.add_assistant_message(response.content or "")
                        
                        # Store tool result
                        result_content = (
                            json.dumps(result.result) if result.success else f"Error: {result.error}"
                        )
                        await self._memory.add_tool_result(
                            tool_name=tool_call.name,
                            tool_call_id=tool_call.id,
                            result=result_content,
                        )
                        
                        # Continue the loop to get next LLM response
                        continue
                    
                    # No tool calls at all - treat as final response
                    await self._memory.add_assistant_message(response.content or "")
                    execution_time = (
                        datetime.now(timezone.utc) - start_time
                    ).total_seconds() * 1000
                    self._status = AgentStatus.IDLE
                    return AgentExecutionResult(
                        success=True,
                        result=response.content,
                        iterations=iterations,
                        total_tokens=total_tokens,
                        execution_time_ms=execution_time,
                    )

            # Max iterations reached
            raise RuntimeError(f"Max iterations reached: {iterations}")

        except Exception as e:
            logger.exception(
                "Agent execution failed",
                agent_id=str(self.agent_id),
                task_id=str(task_id),
                error=str(e),
            )
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self._status = AgentStatus.ERROR
            return AgentExecutionResult(
                success=False,
                error=str(e),
                iterations=iterations,
                total_tokens=total_tokens,
                execution_time_ms=execution_time,
            )
        finally:
            self._current_task_id = None

    async def _build_messages(self, system_prompt: str) -> list[LLMMessage]:
        """Build message list for LLM from memory."""
        from agent_orchestrator.infrastructure.llm.providers.base import ToolCall as LLMToolCall

        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=system_prompt),
        ]

        # Add conversation history from memory
        history = await self._memory.get_context()
        for msg in history:
            # Convert stored tool_calls dicts back to ToolCall objects
            tool_calls = None
            if msg.tool_calls:
                tool_calls = [
                    LLMToolCall(
                        id=tc["id"],
                        type=tc.get("type", "function"),
                        function=tc["function"],
                    )
                    for tc in msg.tool_calls
                ]

            messages.append(
                LLMMessage(
                    role=msg.role,
                    content=msg.content,
                    name=msg.name,
                    tool_call_id=msg.tool_call_id,
                    tool_calls=tool_calls,
                )
            )

        return messages

    async def _handle_tool_calls(
        self,
        response: LLMResponse,
        task_id: UUID,
    ) -> Any | None:
        """Handle tool calls from LLM response."""
        # Convert tool calls to serializable format for storage
        tool_calls_data = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": tc.function,
            }
            for tc in response.tool_calls
        ] if response.tool_calls else None

        # Store assistant message with tool calls
        await self._memory.add_assistant_message(
            response.content or "",
            tool_calls=tool_calls_data,
        )

        # Execute each tool call
        for tc in response.tool_calls:
            tool_call = ToolCall(
                id=tc.id,
                name=tc.function["name"],
                arguments=json.loads(tc.function["arguments"]),
            )

            logger.debug(
                "Executing tool",
                tool_name=tool_call.name,
                agent_id=str(self.agent_id),
            )

            # Check for final_answer tool
            if tool_call.name == "final_answer":
                return tool_call.arguments.get("answer")

            # Execute the tool
            result = await self._tool_executor.execute(tool_call)

            # Emit tool call event
            if self._event_handler:
                await self._event_handler(
                    AgentEvent.tool_call(
                        agent_id=self.agent_id,
                        task_id=task_id,
                        tool_name=tool_call.name,
                        success=result.success,
                        execution_time_ms=result.execution_time_ms,
                    )
                )

            # Store tool result
            result_content = (
                json.dumps(result.result) if result.success else f"Error: {result.error}"
            )
            await self._memory.add_tool_result(
                tool_name=tool_call.name,
                tool_call_id=tool_call.id,
                result=result_content,
            )

        return None

    async def stop(self, graceful: bool = True) -> None:
        """Stop the agent."""
        if graceful and self._current_task_id:
            # Wait for current task to complete
            while self._current_task_id:
                await asyncio.sleep(0.1)
        self._status = AgentStatus.TERMINATED


class AgentRuntimeFactory:
    """Factory for creating agent runtimes."""

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
    ) -> None:
        self._llm_client = llm_client
        self._tool_registry = tool_registry

    def create(
        self,
        definition: AgentDefinition,
        memory: AgentMemory | None = None,
        event_handler: Any | None = None,
    ) -> AgentRuntime:
        """Create an agent runtime from a definition."""
        tool_executor = ToolExecutor(
            self._tool_registry,
            default_timeout=definition.constraints.max_execution_time_seconds,
        )

        return AgentRuntime(
            definition=definition,
            llm_client=self._llm_client,
            tool_registry=self._tool_registry,
            tool_executor=tool_executor,
            memory=memory,
            event_handler=event_handler,
        )
