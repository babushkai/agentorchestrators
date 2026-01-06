"""Sandboxed code execution tool."""

import ast
import asyncio
import sys
from io import StringIO
from typing import Any

import structlog
from pydantic import BaseModel, Field
from RestrictedPython import compile_restricted, safe_builtins
from RestrictedPython.Eval import default_guarded_getiter, default_guarded_getitem
from RestrictedPython.Guards import (
    guarded_iter_unpack_sequence,
    safer_getattr,
)

from agent_orchestrator.core.agents.definition import ToolConfig
from agent_orchestrator.core.agents.tools import Tool

logger = structlog.get_logger(__name__)


class CodeExecutionConfig(BaseModel):
    """Configuration for the code execution tool."""

    max_execution_time_seconds: float = Field(
        default=10.0,
        description="Maximum code execution time.",
    )
    max_output_size: int = Field(
        default=10000,
        description="Maximum output size in characters.",
    )
    max_iterations: int = Field(
        default=100000,
        description="Maximum loop iterations allowed.",
    )
    allowed_imports: set[str] = Field(
        default_factory=lambda: {
            "math",
            "json",
            "datetime",
            "re",
            "collections",
            "itertools",
            "functools",
            "operator",
            "string",
            "random",
            "statistics",
            "decimal",
            "fractions",
        },
        description="Allowed module imports.",
    )


class CodeExecutionTool(Tool):
    """Sandboxed Python code execution tool.

    Uses RestrictedPython for safe code execution with:
    - Limited built-in functions
    - Restricted imports
    - Iteration limits
    - Execution timeout
    """

    def __init__(self, config: CodeExecutionConfig | None = None) -> None:
        tool_config = ToolConfig(
            tool_id="builtin_code_execution",
            name="execute_code",
            description=(
                "Execute Python code in a sandboxed environment. "
                "Allowed modules: math, json, datetime, re, collections, itertools, "
                "functools, operator, string, random, statistics, decimal, fractions. "
                "No file system, network, or subprocess access. "
                "Use print() for output and assign to 'result' variable for return value."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": (
                            "Python code to execute. "
                            "Use print() for output. "
                            "Assign final result to 'result' variable."
                        ),
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Max execution time in seconds (default: 10)",
                    },
                },
                "required": ["code"],
            },
            timeout_seconds=30.0,
        )
        super().__init__(tool_config)
        self._exec_config = config or CodeExecutionConfig()

    async def execute(
        self,
        code: str,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute Python code in sandbox."""
        exec_timeout = timeout or self._exec_config.max_execution_time_seconds

        try:
            # Validate code before execution
            validation_error = self._validate_code(code)
            if validation_error:
                return {"error": validation_error}

            # Compile with RestrictedPython
            byte_code = compile_restricted(
                code,
                filename="<agent_code>",
                mode="exec",
            )

            if byte_code.errors:
                return {
                    "error": "Compilation failed",
                    "details": list(byte_code.errors),
                }

            # Execute with timeout
            result = await asyncio.wait_for(
                self._execute_code(byte_code.code),
                timeout=exec_timeout,
            )

            return result

        except asyncio.TimeoutError:
            return {"error": f"Execution timed out after {exec_timeout}s"}
        except SyntaxError as e:
            return {"error": f"Syntax error: {e}"}
        except Exception as e:
            logger.warning("Code execution failed", error=str(e))
            return {"error": f"Execution failed: {e}"}

    def _validate_code(self, code: str) -> str | None:
        """Validate code before execution."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return f"Syntax error: {e}"

        # Check for dangerous patterns
        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in self._exec_config.allowed_imports:
                        return f"Import not allowed: {alias.name}"

            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] not in self._exec_config.allowed_imports:
                    return f"Import not allowed: {node.module}"

            # Check for exec/eval
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ("exec", "eval", "compile", "__import__"):
                        return f"Function not allowed: {node.func.id}"

            # Check for attribute access to dangerous items
            elif isinstance(node, ast.Attribute):
                if node.attr in ("__class__", "__bases__", "__mro__", "__subclasses__", "__code__", "__globals__"):
                    return f"Attribute access not allowed: {node.attr}"

        return None

    async def _execute_code(self, byte_code: Any) -> dict[str, Any]:
        """Execute compiled code in sandbox."""
        # Capture stdout
        stdout_capture = StringIO()

        # Build restricted globals
        restricted_globals = self._build_restricted_globals(stdout_capture)

        # Build locals for result capture
        restricted_locals: dict[str, Any] = {}

        # Run in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._exec_in_sandbox,
            byte_code,
            restricted_globals,
            restricted_locals,
        )

        # Get output
        output = stdout_capture.getvalue()
        if len(output) > self._exec_config.max_output_size:
            output = output[: self._exec_config.max_output_size] + "\n[Output truncated]"

        # Get result variable if set
        result = restricted_locals.get("result")

        return {
            "output": output,
            "result": result,
            "success": True,
        }

    def _exec_in_sandbox(
        self,
        byte_code: Any,
        globals_dict: dict[str, Any],
        locals_dict: dict[str, Any],
    ) -> None:
        """Execute code in sandbox (runs in thread pool)."""
        exec(byte_code, globals_dict, locals_dict)

    def _build_restricted_globals(self, stdout: StringIO) -> dict[str, Any]:
        """Build restricted globals dictionary."""
        # Start with safe builtins
        restricted_builtins = dict(safe_builtins)

        # Add some safe builtins that RestrictedPython doesn't include by default
        restricted_builtins.update({
            "min": min,
            "max": max,
            "sum": sum,
            "abs": abs,
            "round": round,
            "len": len,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "reversed": reversed,
            "list": list,
            "tuple": tuple,
            "dict": dict,
            "set": set,
            "frozenset": frozenset,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "type": type,
            "isinstance": isinstance,
            "hasattr": hasattr,
            "getattr": safer_getattr,
            "all": all,
            "any": any,
            "chr": chr,
            "ord": ord,
            "hex": hex,
            "oct": oct,
            "bin": bin,
            "pow": pow,
            "divmod": divmod,
            "format": format,
            "repr": repr,
            "id": id,
            "hash": hash,
            "slice": slice,
        })

        # Custom print that writes to our StringIO
        def safe_print(*args: Any, **kwargs: Any) -> None:
            kwargs["file"] = stdout
            print(*args, **kwargs)

        restricted_builtins["print"] = safe_print

        # Create iteration counter for loop limiting
        iteration_count = [0]
        max_iterations = self._exec_config.max_iterations

        def guarded_iter(obj: Any) -> Any:
            """Guard iteration to prevent infinite loops."""
            for item in default_guarded_getiter(obj):
                iteration_count[0] += 1
                if iteration_count[0] > max_iterations:
                    raise RuntimeError(f"Maximum iterations ({max_iterations}) exceeded")
                yield item

        # Build restricted globals
        restricted_globals: dict[str, Any] = {
            "__builtins__": restricted_builtins,
            "_getattr_": safer_getattr,
            "_getitem_": default_guarded_getitem,
            "_getiter_": guarded_iter,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_write_": lambda x: x,  # Allow writes (used for augmented assignment)
            "_print_": safe_print,
        }

        # Add allowed modules
        for module_name in self._exec_config.allowed_imports:
            try:
                module = __import__(module_name)
                restricted_globals[module_name] = module
            except ImportError:
                pass

        return restricted_globals
