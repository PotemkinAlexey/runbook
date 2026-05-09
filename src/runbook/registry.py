"""Explicit registries for reusable checks and actions."""

from __future__ import annotations

from importlib import metadata
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .checks import Check
from .types import Action

CheckFactory = Callable[..., Check]
ActionFactory = Callable[..., Action]
Factory = TypeVar("Factory", CheckFactory, ActionFactory)


class Registry:
    """Named factory registry for embeddable runbook extensions."""

    def __init__(self) -> None:
        self._checks: Dict[str, CheckFactory] = {}
        self._actions: Dict[str, ActionFactory] = {}

    def register_check(self, name: str, factory: CheckFactory, replace: bool = False) -> CheckFactory:
        self._register(self._checks, "check", name, factory, replace)
        return factory

    def register_action(self, name: str, factory: ActionFactory, replace: bool = False) -> ActionFactory:
        self._register(self._actions, "action", name, factory, replace)
        return factory

    def check(self, name: str, *args: Any, **kwargs: Any) -> Check:
        return self._get(self._checks, "check", name)(*args, **kwargs)

    def action(self, name: str, *args: Any, **kwargs: Any) -> Action:
        return self._get(self._actions, "action", name)(*args, **kwargs)

    def list_checks(self) -> List[str]:
        return sorted(self._checks)

    def list_actions(self) -> List[str]:
        return sorted(self._actions)

    @staticmethod
    def _register(
        registry: Dict[str, Factory],
        kind: str,
        name: str,
        factory: Factory,
        replace: bool,
    ) -> None:
        if not name:
            raise ValueError(f"{kind} name must not be empty")
        if name in registry and not replace:
            raise ValueError(f"{kind} already registered: {name}")
        registry[name] = factory

    @staticmethod
    def _get(registry: Dict[str, Factory], kind: str, name: str) -> Factory:
        try:
            return registry[name]
        except KeyError:
            raise KeyError(f"unknown {kind}: {name}") from None


default_registry = Registry()


def register_check(
    name: str,
    factory: Optional[CheckFactory] = None,
    replace: bool = False,
) -> Any:
    """Register a check factory on the default registry."""

    def decorator(fn: CheckFactory) -> CheckFactory:
        return default_registry.register_check(name, fn, replace=replace)

    if factory is not None:
        return decorator(factory)
    return decorator


def register_action(
    name: str,
    factory: Optional[ActionFactory] = None,
    replace: bool = False,
) -> Any:
    """Register an action factory on the default registry."""

    def decorator(fn: ActionFactory) -> ActionFactory:
        return default_registry.register_action(name, fn, replace=replace)

    if factory is not None:
        return decorator(factory)
    return decorator


def get_registered_check(name: str, *args: Any, **kwargs: Any) -> Check:
    return default_registry.check(name, *args, **kwargs)


def get_registered_action(name: str, *args: Any, **kwargs: Any) -> Action:
    return default_registry.action(name, *args, **kwargs)


def list_registered_checks() -> List[str]:
    return default_registry.list_checks()


def list_registered_actions() -> List[str]:
    return default_registry.list_actions()


def load_registry_entry_points(group: str = "runbook.plugins", registry: Optional[Registry] = None) -> List[str]:
    """Load registry plugins from Python entry points.

    Each entry point should resolve to a callable that accepts a `Registry`.
    """

    target_registry = registry or default_registry
    loaded: List[str] = []
    for entry_point in _entry_points_for_group(group):
        plugin = entry_point.load()
        plugin(target_registry)
        loaded.append(entry_point.name)
    return loaded


def _entry_points_for_group(group: str):
    entry_points = metadata.entry_points()
    if hasattr(entry_points, "select"):
        return entry_points.select(group=group)
    return entry_points.get(group, [])
