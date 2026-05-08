"""Execution results for runbooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .exceptions import RunbookFailedError
from .types import Context


@dataclass(frozen=True)
class StepResult:
    """Result of a single executed step."""

    name: str
    status: str = "passed"

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    @property
    def failed(self) -> bool:
        return self.status == "failed"


@dataclass(frozen=True)
class RunbookResult:
    """Result of a runbook execution."""

    name: Optional[str]
    status: str
    context: Context
    steps: List[StepResult] = field(default_factory=list)
    error: Optional[RunbookFailedError] = None

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    @property
    def failed(self) -> bool:
        return self.status == "failed"

    @classmethod
    def success(cls, name: Optional[str], context: Context, steps: List[StepResult]) -> "RunbookResult":
        return cls(name=name, status="passed", context=context, steps=steps)

    @classmethod
    def failure(
        cls,
        name: Optional[str],
        context: Context,
        steps: List[StepResult],
        error: RunbookFailedError,
    ) -> "RunbookResult":
        return cls(name=name, status="failed", context=context, steps=steps, error=error)
