"""Safe AST Formula Service.

Evaluates mathematical formulas safely using Python AST without using unsafe eval().
"""

import ast
import logging
import operator
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class FormulaSecurityError(ValueError):
    """Raised when an unsupported or unsafe node is found in the formula expression."""

    pass


class FormulaService:
    """Evaluates mathematical expressions safely using AST parsing."""

    SAFE_FUNCTIONS: dict[str, Callable[..., Any]] = {
        "sum": lambda *args: sum(args[0]) if len(args) == 1 and isinstance(args[0], (list, tuple)) else sum(args),
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
    }

    BINARY_OPERATORS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    @classmethod
    def evaluate(cls, expression: str, row_data: dict[str, Any]) -> float | int | str:
        """Safely evaluates a formula expression against row data context.

        Args:
            expression: Math formula string (e.g. "alacak - borç" or "(borç / (alacak + borç)) * 100").
            row_data: Row values mapping field names to numerical values.

        Returns:
            Computed numerical value or error indicator.
        """
        if not expression or not expression.strip():
            return 0.0

        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = cls._eval_node(tree.body, row_data)
            return result
        except FormulaSecurityError:
            raise
        except ZeroDivisionError:
            return 0.0
        except Exception as e:
            logger.debug(f"Formula evaluation warning for '{expression}': {e}")
            return 0.0

    @classmethod
    def _eval_node(cls, node: ast.AST, context: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            return 0.0

        elif isinstance(node, ast.Name):
            var_name = node.id
            if var_name in context:
                val = context[var_name]
                try:
                    return float(val) if val is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0
            return 0.0

        elif isinstance(node, ast.BinOp):
            left = cls._eval_node(node.left, context)
            right = cls._eval_node(node.right, context)
            op_type = type(node.op)
            if op_type in cls.BINARY_OPERATORS:
                if op_type == ast.Div and right == 0:
                    return 0.0
                return cls.BINARY_OPERATORS[op_type](left, right)
            raise FormulaSecurityError(f"Unsupported binary operator: {op_type}")

        elif isinstance(node, ast.UnaryOp):
            operand = cls._eval_node(node.operand, context)
            op_type = type(node.op)
            if op_type in cls.UNARY_OPERATORS:
                return cls.UNARY_OPERATORS[op_type](operand)
            raise FormulaSecurityError(f"Unsupported unary operator: {op_type}")

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in cls.SAFE_FUNCTIONS:
                    args = [cls._eval_node(arg, context) for arg in node.args]
                    return cls.SAFE_FUNCTIONS[func_name](*args)
            raise FormulaSecurityError(f"Unsafe function call: {ast.dump(node)}")

        else:
            raise FormulaSecurityError(f"Forbidden node type in formula: {type(node)}")
