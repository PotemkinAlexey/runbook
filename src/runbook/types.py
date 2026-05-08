"""Shared public types for runbook extensions."""

from __future__ import annotations

from typing import Any, Callable, Dict

Context = Dict[str, Any]
Action = Callable[[Context], Any]
Loader = Callable[[Context], Any]
ContextModifier = Callable[[Context], Any]
