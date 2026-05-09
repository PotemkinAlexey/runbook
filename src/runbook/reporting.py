"""Human-readable reporting helpers."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from .core import Runbook, Stage
from .exceptions import RunbookFailedError
from .result import RunbookResult, StageResult, StepResult
from .types import Context

DEFAULT_SECRET_KEYS = ("password", "secret", "token", "api_key", "apikey", "access_key")


def format_failure(
    error: RunbookFailedError,
    context: Optional[Context] = None,
    runbook_name: Optional[str] = None,
    max_value_length: int = 200,
    secret_keys: Iterable[str] = DEFAULT_SECRET_KEYS,
) -> str:
    lines = []
    if runbook_name:
        lines.append(f"Runbook: {runbook_name}")
    path = getattr(error, "path", None)
    if path:
        full_path = [runbook_name] if runbook_name else []
        full_path.extend(path)
        lines.append(f"Path: {' > '.join(full_path)}")
    lines.extend(
        [
            f"Step: {error.step_name}",
            f"Condition: {error.condition}",
            f"Message: {error.message}",
        ]
    )

    if context:
        lines.append("Context:")
        for key in sorted(context):
            lines.append(f"  {key}: {_format_value(key, context[key], max_value_length, secret_keys)}")

    return "\n".join(lines)


def format_runbook_tree(runbook: Runbook) -> str:
    lines = [runbook.name or "<unnamed>"]
    for child in runbook.steps:
        _append_definition_node(lines, child, level=1)
    return "\n".join(lines)


def format_result_tree(result: RunbookResult) -> str:
    lines = [f"{_status_marker(result.status)} {result.name or '<unnamed>'}"]
    for child in result.children:
        _append_result_node(lines, child, level=1)
    return "\n".join(lines)


def _append_definition_node(lines: list[str], node: Any, level: int) -> None:
    indent = "  " * level
    if isinstance(node, Stage):
        lines.append(f"{indent}- {node.name}/")
        for child in node.children:
            _append_definition_node(lines, child, level + 1)
        return
    lines.append(f"{indent}- {node.name}")


def _append_result_node(lines: list[str], node: Any, level: int) -> None:
    indent = "  " * level
    if isinstance(node, StageResult):
        lines.append(f"{indent}{_status_marker(node.status)} {node.name}/")
        for child in node.children:
            _append_result_node(lines, child, level + 1)
        return
    if isinstance(node, StepResult):
        suffix = f" - {node.message}" if node.message else ""
        lines.append(f"{indent}{_status_marker(node.status)} {node.name}{suffix}")
        return
    lines.append(f"{indent}? {getattr(node, 'name', '<unknown>')}")


def _status_marker(status: str) -> str:
    if status == "passed":
        return "PASS"
    if status == "failed":
        return "FAIL"
    if status == "skipped":
        return "SKIP"
    return status.upper()


def _format_value(key: str, value: Any, max_value_length: int, secret_keys: Iterable[str]) -> str:
    if _is_secret_key(key, secret_keys):
        return "***"

    value_repr = repr(value)
    if len(value_repr) <= max_value_length:
        return value_repr
    return value_repr[: max_value_length - 3] + "..."


def _is_secret_key(key: str, secret_keys: Iterable[str]) -> bool:
    normalized = key.lower()
    return any(secret_key in normalized for secret_key in secret_keys)
