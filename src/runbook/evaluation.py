"""Expression evaluation helpers."""

from __future__ import annotations

from typing import Any, Dict

from .exceptions import StepExecutionError


def safe_eval(expr: str, context: Dict[str, Any]) -> Any:
    """Evaluate a Python expression with a restricted global namespace."""
    try:
        return eval(expr, {}, context)
    except Exception as exc:
        raise StepExecutionError(expr, exc) from exc
