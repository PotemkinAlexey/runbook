"""Runbook execution logging."""

from __future__ import annotations

import logging
from typing import Optional

RUNBOOK_LOGGER_NAME = "runbook"


def configure_runbook_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure a simple console logger for runbook execution messages."""
    logger = logging.getLogger(RUNBOOK_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    if _has_only_null_handlers(logger):
        logger.handlers = []

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    return logger


def get_runbook_logger() -> "RunbookLogger":
    logger = logging.getLogger(RUNBOOK_LOGGER_NAME)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return RunbookLogger(logger)


class RunbookLogger:
    """Small formatting layer for human-readable execution logs."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(RUNBOOK_LOGGER_NAME)

    def runbook_started(self, name: Optional[str], step_count: int) -> None:
        self.logger.info("runbook | start: %s (%s steps)", _name(name), step_count)

    def runbook_passed(self, name: Optional[str], step_count: int) -> None:
        self.logger.info("runbook | pass: %s (%s steps)", _name(name), step_count)

    def runbook_failed(self, name: Optional[str], step_name: str, condition: str) -> None:
        self.logger.error("runbook | fail: %s at %s [%s]", _name(name), step_name, condition)

    def step_started(self, name: str, index: Optional[int] = None, total: Optional[int] = None) -> None:
        prefix = _step_prefix(index, total)
        self.logger.info("runbook | %sstart: %s", prefix, name)

    def step_passed(self, name: str) -> None:
        self.logger.info("runbook | step pass: %s", name)

    def step_skipped(self, name: str, message: Optional[str]) -> None:
        suffix = f" - {message}" if message else ""
        self.logger.info("runbook | step skip: %s%s", name, suffix)

    def step_failed(self, name: str, condition: str) -> None:
        self.logger.error("runbook | step fail: %s [%s]", name, condition)

    def step_retry(self, name: str, attempt: int, total: int, condition: str) -> None:
        self.logger.warning("runbook | step retry: %s attempt %s/%s after [%s]", name, attempt, total, condition)

    def step_warning(self, name: str, message: str) -> None:
        self.logger.warning("runbook | step warn: %s - %s", name, message)

    def check_started(self, kind: str, name: str) -> None:
        self.logger.info("runbook | check %s: %s", kind, name)

    def expand_empty(self, key: Optional[str]) -> None:
        self.logger.info("runbook | expand %s: no items", key)

    def expand_started(self, key: Optional[str], count: int) -> None:
        self.logger.info("runbook | expand %s: %s items", key, count)

    def handler_failed(self, label: str, error: Exception) -> None:
        self.logger.error("runbook | handler fail: %s - %s", label, error)

def _name(name: Optional[str]) -> str:
    return name or "<unnamed>"


def _step_prefix(index: Optional[int], total: Optional[int]) -> str:
    if index is None or total is None:
        return "step "
    return f"step {index}/{total} "


def _has_only_null_handlers(logger: logging.Logger) -> bool:
    return bool(logger.handlers) and all(isinstance(handler, logging.NullHandler) for handler in logger.handlers)
