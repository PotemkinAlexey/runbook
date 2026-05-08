"""Expression evaluation helpers."""

from __future__ import annotations

from typing import Any

from .exceptions import StepExecutionError
from .types import Context


def safe_eval(expr: str, context: Context) -> Any:
    """Evaluate a Python expression with a restricted global namespace."""
    try:
        return eval(expr, {}, context)
    except Exception as exc:
        raise StepExecutionError(expr, exc) from exc
