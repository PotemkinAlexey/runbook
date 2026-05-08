"""Declarative checks for runbook requirements."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any, Callable, Iterable

from .types import Context


@dataclass(frozen=True)
class Check:
    name: str
    predicate: Callable[[Context], bool]

    def __call__(self, context: Context) -> bool:
        return bool(self.predicate(context))


def exists(key: str) -> Check:
    return Check(f"exists({key})", lambda context: _get(context, key) is not None)


def missing(key: str) -> Check:
    return Check(f"missing({key})", lambda context: _get(context, key) is None)


def not_empty(key: str) -> Check:
    return Check(f"not_empty({key})", lambda context: bool(_get(context, key)))


def empty(key: str) -> Check:
    return Check(f"empty({key})", lambda context: not bool(_get(context, key)))


def equals(key: str, expected: Any) -> Check:
    return Check(f"equals({key}, {expected!r})", lambda context: _get(context, key) == expected)


def gt(key: str, threshold: Any) -> Check:
    return Check(f"gt({key}, {threshold!r})", lambda context: _get(context, key) > threshold)


def gte(key: str, threshold: Any) -> Check:
    return Check(f"gte({key}, {threshold!r})", lambda context: _get(context, key) >= threshold)


def lt(key: str, threshold: Any) -> Check:
    return Check(f"lt({key}, {threshold!r})", lambda context: _get(context, key) < threshold)


def lte(key: str, threshold: Any) -> Check:
    return Check(f"lte({key}, {threshold!r})", lambda context: _get(context, key) <= threshold)


def contains(key: str, expected: Any) -> Check:
    return Check(f"contains({key}, {expected!r})", lambda context: expected in _get(context, key))


def matches_any(key: str, pattern: str) -> Check:
    def predicate(context: Context) -> bool:
        values = _get(context, key) or []
        if isinstance(values, str):
            values = [values]
        return any(fnmatch(str(value), pattern) for value in values)

    return Check(f"matches_any({key}, {pattern!r})", predicate)


def all_of(*checks: Check) -> Check:
    return Check(_join_name("all_of", checks), lambda context: all(check(context) for check in checks))


def any_of(*checks: Check) -> Check:
    return Check(_join_name("any_of", checks), lambda context: any(check(context) for check in checks))


def not_(check: Check) -> Check:
    return Check(f"not_({check.name})", lambda context: not check(context))


def custom(name: str, predicate: Callable[[Context], bool]) -> Check:
    return Check(name, predicate)


def _get(context: Context, key: str) -> Any:
    value: Any = context
    for part in key.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
        if value is None:
            return None
    return value


def _join_name(name: str, checks: Iterable[Check]) -> str:
    return f"{name}({', '.join(check.name for check in checks)})"
