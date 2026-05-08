"""Expression evaluation helpers."""

from __future__ import annotations

import ast
import operator
from typing import Any

from .exceptions import StepExecutionError
from .types import Context

SAFE_FUNCTIONS = {
    "all": all,
    "any": any,
    "bool": bool,
    "float": float,
    "int": int,
    "len": len,
    "max": max,
    "min": min,
    "str": str,
    "sum": sum,
}

BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def safe_eval(expr: str, context: Context) -> Any:
    """Evaluate a small, safe subset of Python expressions against context."""
    try:
        parsed = ast.parse(expr, mode="eval")
        return _eval_node(parsed.body, context)
    except Exception as exc:
        raise StepExecutionError(expr, exc) from exc


def _eval_node(node: ast.AST, context: Context) -> Any:
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id in context:
            return context[node.id]
        if node.id in SAFE_FUNCTIONS:
            return SAFE_FUNCTIONS[node.id]
        raise NameError(f"name `{node.id}` is not defined")

    if isinstance(node, ast.List):
        return [_eval_node(item, context) for item in node.elts]

    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(item, context) for item in node.elts)

    if isinstance(node, ast.Dict):
        return {_eval_node(key, context): _eval_node(value, context) for key, value in zip(node.keys, node.values)}

    if isinstance(node, ast.BoolOp):
        values = [_eval_node(value, context) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise ValueError(f"unsupported boolean operator: {type(node.op).__name__}")

    if isinstance(node, ast.UnaryOp):
        value = _eval_node(node.operand, context)
        if isinstance(node.op, ast.Not):
            return not value
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value
        raise ValueError(f"unsupported unary operator: {type(node.op).__name__}")

    if isinstance(node, ast.BinOp):
        operation = BIN_OPS.get(type(node.op))
        if operation is None:
            raise ValueError(f"unsupported binary operator: {type(node.op).__name__}")
        return operation(_eval_node(node.left, context), _eval_node(node.right, context))

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, context)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, context)
            if isinstance(op, ast.In):
                result = left in right
            elif isinstance(op, ast.NotIn):
                result = left not in right
            elif isinstance(op, ast.Is):
                result = left is right
            elif isinstance(op, ast.IsNot):
                result = left is not right
            else:
                operation = COMPARE_OPS.get(type(op))
                if operation is None:
                    raise ValueError(f"unsupported comparison operator: {type(op).__name__}")
                result = operation(left, right)
            if not result:
                return False
            left = right
        return True

    if isinstance(node, ast.Subscript):
        return _eval_node(node.value, context)[_eval_node(node.slice, context)]

    if isinstance(node, ast.Attribute):
        attr = node.attr
        if attr.startswith("_"):
            raise ValueError("private attribute access is not allowed")
        value = _eval_node(node.value, context)
        if isinstance(value, dict):
            return value[attr]
        return getattr(value, attr)

    if isinstance(node, ast.Call):
        func = _eval_node(node.func, context)
        if func not in SAFE_FUNCTIONS.values():
            raise ValueError("only safe built-in calls are allowed")
        args = [_eval_node(arg, context) for arg in node.args]
        kwargs = {keyword.arg: _eval_node(keyword.value, context) for keyword in node.keywords}
        return func(*args, **kwargs)

    raise ValueError(f"unsupported expression node: {type(node).__name__}")
