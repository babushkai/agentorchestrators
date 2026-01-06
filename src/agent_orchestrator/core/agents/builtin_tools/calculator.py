"""Calculator tool for safe mathematical expression evaluation."""

import ast
import math
import operator
from typing import Any

import structlog

from agent_orchestrator.core.agents.definition import ToolConfig
from agent_orchestrator.core.agents.tools import Tool

logger = structlog.get_logger(__name__)


class CalculatorTool(Tool):
    """Safe mathematical calculator using AST parsing.

    Evaluates mathematical expressions safely without using eval().
    Supports basic arithmetic, power, modulo, and common math functions.
    """

    # Supported binary operators
    BINARY_OPS: dict[type, Any] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    # Supported unary operators
    UNARY_OPS: dict[type, Any] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    # Supported math functions
    MATH_FUNCTIONS: dict[str, Any] = {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
        "sinh": math.sinh,
        "cosh": math.cosh,
        "tanh": math.tanh,
        "sqrt": math.sqrt,
        "log": math.log,
        "log10": math.log10,
        "log2": math.log2,
        "exp": math.exp,
        "floor": math.floor,
        "ceil": math.ceil,
        "abs": abs,
        "round": round,
        "pow": pow,
        "min": min,
        "max": max,
    }

    # Constants
    CONSTANTS: dict[str, float] = {
        "pi": math.pi,
        "e": math.e,
        "tau": math.tau,
        "inf": math.inf,
    }

    def __init__(self, precision: int = 10) -> None:
        config = ToolConfig(
            tool_id="builtin_calculator",
            name="calculator",
            description=(
                "Perform mathematical calculations safely. "
                "Supports: +, -, *, /, //, %, ** (power), and functions like "
                "sin, cos, tan, sqrt, log, exp, floor, ceil, abs, round, min, max. "
                "Constants: pi, e, tau."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": (
                            "Mathematical expression to evaluate. "
                            "Examples: '2 + 2', 'sqrt(16)', 'sin(pi/2)', '2**10'"
                        ),
                    },
                    "precision": {
                        "type": "integer",
                        "description": "Decimal precision for the result (default: 10)",
                        "default": 10,
                    },
                },
                "required": ["expression"],
            },
        )
        super().__init__(config)
        self._default_precision = precision

    async def execute(self, expression: str, precision: int | None = None) -> dict[str, Any]:
        """Execute the calculator with the given expression."""
        try:
            result = self._safe_eval(expression)
            prec = precision or self._default_precision

            # Round floating point results
            if isinstance(result, float):
                result = round(result, prec)
                # Convert to int if it's a whole number
                if result == int(result):
                    result = int(result)

            logger.debug(
                "Calculator evaluation",
                expression=expression,
                result=result,
            )

            return {
                "expression": expression,
                "result": result,
                "type": type(result).__name__,
            }

        except ZeroDivisionError:
            return {
                "expression": expression,
                "error": "Division by zero",
            }
        except ValueError as e:
            return {
                "expression": expression,
                "error": f"Math domain error: {e}",
            }
        except Exception as e:
            logger.warning(
                "Calculator evaluation failed",
                expression=expression,
                error=str(e),
            )
            return {
                "expression": expression,
                "error": f"Invalid expression: {e}",
            }

    def _safe_eval(self, expression: str) -> float | int:
        """Safely evaluate a mathematical expression using AST parsing."""
        # Parse the expression
        tree = ast.parse(expression, mode="eval")
        return self._eval_node(tree.body)

    def _eval_node(self, node: ast.AST) -> float | int:
        """Recursively evaluate an AST node."""
        match node:
            case ast.Constant(value=value) if isinstance(value, (int, float)):
                return value

            case ast.Name(id=name):
                # Check if it's a constant
                if name in self.CONSTANTS:
                    return self.CONSTANTS[name]
                raise ValueError(f"Unknown variable: {name}")

            case ast.BinOp(left=left, op=op, right=right):
                op_func = self.BINARY_OPS.get(type(op))
                if op_func is None:
                    raise ValueError(f"Unsupported operator: {type(op).__name__}")
                return op_func(self._eval_node(left), self._eval_node(right))

            case ast.UnaryOp(op=op, operand=operand):
                op_func = self.UNARY_OPS.get(type(op))
                if op_func is None:
                    raise ValueError(f"Unsupported unary operator: {type(op).__name__}")
                return op_func(self._eval_node(operand))

            case ast.Call(func=ast.Name(id=func_name), args=args, keywords=_):
                if func_name not in self.MATH_FUNCTIONS:
                    raise ValueError(f"Unknown function: {func_name}")
                func = self.MATH_FUNCTIONS[func_name]
                evaluated_args = [self._eval_node(arg) for arg in args]
                return func(*evaluated_args)

            case ast.Compare():
                # Support for comparisons (returns 1 for True, 0 for False)
                raise ValueError("Comparison operators are not supported")

            case _:
                raise ValueError(f"Unsupported expression type: {type(node).__name__}")
