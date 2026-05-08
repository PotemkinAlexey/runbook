"""Human-readable reporting helpers."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from .exceptions import RunbookFailedError
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
