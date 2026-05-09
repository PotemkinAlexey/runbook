"""Result exporters for lightweight observability."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .result import RunbookResult

ResultExporter = Callable[[RunbookResult], None]


class JsonlResultExporter:
    """Append one serialized runbook result per line."""

    def __init__(self, path: str, include_context: bool = False, encoding: str = "utf-8") -> None:
        self.path = Path(path)
        self.include_context = include_context
        self.encoding = encoding

    def __call__(self, result: RunbookResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding=self.encoding) as handle:
            handle.write(result.to_json(include_context=self.include_context))
            handle.write("\n")
