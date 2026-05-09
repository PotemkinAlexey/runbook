"""Result exporters for lightweight observability."""

from __future__ import annotations

from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Callable

from .result import RunbookResult

ResultExporter = Callable[[RunbookResult], None]
_SENTINEL = object()


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


class AsyncResultExporter:
    """Run a result exporter in a background worker thread."""

    def __init__(self, exporter: ResultExporter, max_queue_size: int = 0) -> None:
        self.exporter = exporter
        self.errors: list[Exception] = []
        self._queue: Queue = Queue(maxsize=max_queue_size)
        self._closed = False
        self._worker = Thread(target=self._run, name="runbook-result-exporter", daemon=True)
        self._worker.start()

    def __call__(self, result: RunbookResult) -> None:
        if self._closed:
            raise RuntimeError("async result exporter is closed")
        self._queue.put(result)

    def flush(self) -> None:
        self._queue.join()

    def close(self) -> None:
        if self._closed:
            return
        self.flush()
        self._closed = True
        self._queue.put(_SENTINEL)
        self._worker.join()

    def __enter__(self) -> "AsyncResultExporter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is _SENTINEL:
                    return
                self.exporter(item)
            except Exception as exc:  # pragma: no cover - defensive background path
                self.errors.append(exc)
            finally:
                self._queue.task_done()
