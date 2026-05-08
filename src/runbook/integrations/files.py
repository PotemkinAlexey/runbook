"""Portable local filesystem integrations."""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any

from jinja2 import Template

from runbook.types import Context


def glob_paths(pattern: str, recursive: bool = False):
    """Return a loader that lists paths matching a glob pattern."""

    def loader(context: Context) -> list[str]:
        rendered_pattern = _render(pattern, context)
        return sorted(glob.glob(rendered_pattern, recursive=recursive))

    return loader


def path_exists(path: str):
    """Return a loader that checks whether a path exists."""

    def loader(context: Context) -> bool:
        return Path(_render(path, context)).exists()

    return loader


def read_text(path: str, encoding: str = "utf-8"):
    """Return a loader that reads text from a file."""

    def loader(context: Context) -> str:
        return Path(_render(path, context)).read_text(encoding=encoding)

    return loader


def read_json(path: str, encoding: str = "utf-8"):
    """Return a loader that reads JSON from a file."""

    def loader(context: Context) -> Any:
        return json.loads(Path(_render(path, context)).read_text(encoding=encoding))

    return loader


def write_json(path: str, value_key: str, encoding: str = "utf-8", indent: int = 2):
    """Return an action that writes a context value as JSON."""

    def action(context: Context) -> None:
        output_path = Path(_render(path, context))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(context[value_key], indent=indent, default=str), encoding=encoding)

    return action


def _render(value: str, context: Context) -> str:
    return Template(value).render(context)
