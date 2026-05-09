"""Execution results for runbooks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union

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

    def to_dict(self, path: Optional[List[str]] = None) -> dict[str, Any]:
        node_path = path or [self.name]
        return {
            "type": "step",
            "name": self.name,
            "path": node_path,
            "status": self.status,
            "message": self.message,
            "warnings": list(self.warnings),
            "duration_seconds": self.duration_seconds,
        }


ResultNode = Union["StageResult", StepResult]


@dataclass(frozen=True)
class StageResult:
    """Result of a stage execution."""

    name: str
    status: str
    children: List[ResultNode] = field(default_factory=list)
    message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    duration_seconds: Optional[float] = None
    error: Optional[RunbookFailedError] = None

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
        return bool(self.warnings) or any(child.warned for child in self.children)

    def find(self, name: str) -> Optional[ResultNode]:
        if self.name == name:
            return self
        for child in self.children:
            if child.name == name:
                return child
            if isinstance(child, StageResult):
                found = child.find(name)
                if found is not None:
                    return found
        return None

    def to_dict(self, path: Optional[List[str]] = None) -> dict[str, Any]:
        node_path = path or [self.name]
        return {
            "type": "stage",
            "name": self.name,
            "path": node_path,
            "status": self.status,
            "message": self.message,
            "warnings": list(self.warnings),
            "duration_seconds": self.duration_seconds,
            "children": [child.to_dict(path=node_path + [child.name]) for child in self.children],
            "error": _error_to_dict(self.error),
        }

    @classmethod
    def success(
        cls,
        name: str,
        children: List[ResultNode],
        warnings: Optional[List[str]] = None,
        duration_seconds: Optional[float] = None,
    ) -> "StageResult":
        return cls(
            name=name,
            status="passed",
            children=children,
            warnings=warnings or [],
            duration_seconds=duration_seconds,
        )

    @classmethod
    def failure(
        cls,
        name: str,
        children: List[ResultNode],
        error: RunbookFailedError,
        warnings: Optional[List[str]] = None,
        duration_seconds: Optional[float] = None,
    ) -> "StageResult":
        return cls(
            name=name,
            status="failed",
            children=children,
            warnings=warnings or [],
            error=error,
            duration_seconds=duration_seconds,
        )


@dataclass(frozen=True)
class RunbookResult:
    """Result of a runbook execution."""

    name: Optional[str]
    status: str
    context: Context
    steps: List[StepResult] = field(default_factory=list)
    children: List[ResultNode] = field(default_factory=list)
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
        return sum(1 for step in _flatten_steps(self.children) if step.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for step in _flatten_steps(self.children) if step.failed)

    @property
    def skipped_count(self) -> int:
        return sum(1 for step in _flatten_steps(self.children) if step.skipped)

    @property
    def warned_count(self) -> int:
        return sum(1 for step in _flatten_steps(self.children) if step.warned)

    def find(self, name: str) -> Optional[ResultNode]:
        if self.name == name:
            return self
        for child in self.children:
            if child.name == name:
                return child
            if isinstance(child, StageResult):
                found = child.find(name)
                if found is not None:
                    return found
        return None

    def to_dict(self, include_context: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
            "summary": {
                "total": len(_flatten_steps(self.children)),
                "passed": self.passed_count,
                "failed": self.failed_count,
                "skipped": self.skipped_count,
                "warned": self.warned_count,
                "duration_seconds": self.duration_seconds,
            },
            "children": [
                child.to_dict(path=_root_path(self.name) + [child.name])
                for child in self.children
            ],
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
        steps: Optional[List[StepResult]] = None,
        children: Optional[List[ResultNode]] = None,
        duration_seconds: Optional[float] = None,
    ) -> "RunbookResult":
        children = children if children is not None else list(steps or [])
        steps = steps if steps is not None else _flatten_steps(children)
        return cls(
            name=name,
            status="passed",
            context=context,
            steps=steps,
            children=children,
            duration_seconds=duration_seconds,
        )

    @classmethod
    def failure(
        cls,
        name: Optional[str],
        context: Context,
        error: RunbookFailedError,
        steps: Optional[List[StepResult]] = None,
        children: Optional[List[ResultNode]] = None,
        duration_seconds: Optional[float] = None,
    ) -> "RunbookResult":
        children = children if children is not None else list(steps or [])
        steps = steps if steps is not None else _flatten_steps(children)
        return cls(
            name=name,
            status="failed",
            context=context,
            steps=steps,
            children=children,
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


def _root_path(name: Optional[str]) -> List[str]:
    return [name] if name else []


def _flatten_steps(children: List[ResultNode]) -> List[StepResult]:
    steps: List[StepResult] = []
    for child in children:
        if isinstance(child, StepResult):
            steps.append(child)
        else:
            steps.extend(_flatten_steps(child.children))
    return steps
