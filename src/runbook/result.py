"""Execution results for runbooks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, List, Optional

from .exceptions import RunbookFailedError
from .types import Context


@dataclass(frozen=True)
class StepResult:
    """Result of a single executed step."""

    name: str
    status: str = "passed"
    message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    duration_seconds: Optional[float] = None

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    @property
    def failed(self) -> bool:
        return self.status == "failed"

    @property
    def skipped(self) -> bool:
        return self.status == "skipped"

    @property
    def warned(self) -> bool:
        return bool(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "warnings": list(self.warnings),
            "duration_seconds": self.duration_seconds,
        }


@dataclass(frozen=True)
class RunbookResult:
    """Result of a runbook execution."""

    name: Optional[str]
    status: str
    context: Context
    steps: List[StepResult] = field(default_factory=list)
    error: Optional[RunbookFailedError] = None
    duration_seconds: Optional[float] = None

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    @property
    def failed(self) -> bool:
        return self.status == "failed"

    @property
    def passed_count(self) -> int:
        return sum(1 for step in self.steps if step.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for step in self.steps if step.failed)

    @property
    def skipped_count(self) -> int:
        return sum(1 for step in self.steps if step.skipped)

    @property
    def warned_count(self) -> int:
        return sum(1 for step in self.steps if step.warned)

    def to_dict(self, include_context: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
            "summary": {
                "total": len(self.steps),
                "passed": self.passed_count,
                "failed": self.failed_count,
                "skipped": self.skipped_count,
                "warned": self.warned_count,
                "duration_seconds": self.duration_seconds,
            },
            "steps": [step.to_dict() for step in self.steps],
            "error": _error_to_dict(self.error),
        }
        if include_context:
            data["context"] = self.context
        return data

    def to_json(self, include_context: bool = False, **json_kwargs: Any) -> str:
        kwargs = {"default": str}
        kwargs.update(json_kwargs)
        return json.dumps(self.to_dict(include_context=include_context), **kwargs)

    @classmethod
    def success(
        cls,
        name: Optional[str],
        context: Context,
        steps: List[StepResult],
        duration_seconds: Optional[float] = None,
    ) -> "RunbookResult":
        return cls(name=name, status="passed", context=context, steps=steps, duration_seconds=duration_seconds)

    @classmethod
    def failure(
        cls,
        name: Optional[str],
        context: Context,
        steps: List[StepResult],
        error: RunbookFailedError,
        duration_seconds: Optional[float] = None,
    ) -> "RunbookResult":
        return cls(
            name=name,
            status="failed",
            context=context,
            steps=steps,
            error=error,
            duration_seconds=duration_seconds,
        )


def _error_to_dict(error: Optional[RunbookFailedError]) -> Optional[dict[str, str]]:
    if error is None:
        return None
    return {
        "step_name": error.step_name,
        "condition": error.condition,
        "message": error.message,
    }
