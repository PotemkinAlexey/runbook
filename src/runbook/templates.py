"""Template rendering helpers."""

from __future__ import annotations

from functools import lru_cache

from jinja2 import Template

from .types import Context


def render_template(template: str, context: Context) -> str:
    return _compile_template(template).render(context)


@lru_cache(maxsize=512)
def _compile_template(template: str) -> Template:
    return Template(template)
