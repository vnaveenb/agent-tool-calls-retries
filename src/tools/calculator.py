from __future__ import annotations

import ast
import operator

from .base import ToolResult

# Whitelist of allowed AST node types for safe arithmetic evaluation
_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
)

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float:
    """Recursively evaluate a whitelisted AST node."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_BINOPS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        # Prevent unreasonably large exponents
        if op_type is ast.Pow and right > 1000:
            raise ValueError("Exponent too large (max 1000)")
        return _ALLOWED_BINOPS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_UNARYOPS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return _ALLOWED_UNARYOPS[op_type](_safe_eval(node.operand))

    raise ValueError(f"Unsupported expression element: {type(node).__name__}")


def calculate(expression: str) -> ToolResult:
    """Safely evaluate an arithmetic expression.

    Only allows: numbers, +, -, *, /, //, %, **, parentheses, unary +/-.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")

        # Validate all nodes are in the whitelist
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED_NODES + (ast.Add, ast.Sub, ast.Mult,
                              ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
                              ast.UAdd, ast.USub)):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unsafe expression element: {type(node).__name__}. "
                          "Only arithmetic operations are allowed.",
                )

        result = _safe_eval(tree)

        # Format: remove trailing .0 for integers
        if isinstance(result, float) and result == int(result) and abs(result) < 1e15:
            formatted = str(int(result))
        else:
            formatted = str(result)

        return ToolResult(success=True, output=formatted)

    except (SyntaxError, ValueError) as e:
        return ToolResult(success=False, output="", error=str(e))
    except ZeroDivisionError:
        return ToolResult(success=False, output="", error="Division by zero")
    except OverflowError:
        return ToolResult(success=False, output="", error="Result too large (overflow)")
