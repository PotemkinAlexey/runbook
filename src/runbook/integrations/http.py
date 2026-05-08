"""Portable HTTP integrations built on the Python standard library."""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib import request

from runbook.templates import render_template
from runbook.types import Context


def get_text(url: str, headers: Optional[dict[str, str]] = None, timeout: float = 30.0):
    """Return a loader that performs an HTTP GET and returns text."""

    def loader(context: Context) -> str:
        response = _open("GET", _render(url, context), headers=_render_mapping(headers or {}, context), timeout=timeout)
        return response.decode("utf-8")

    return loader


def get_json(url: str, headers: Optional[dict[str, str]] = None, timeout: float = 30.0):
    """Return a loader that performs an HTTP GET and parses JSON."""

    def loader(context: Context) -> Any:
        return json.loads(get_text(url, headers=headers, timeout=timeout)(context))

    return loader


def post_json(
    url: str,
    payload_key: str,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 30.0,
):
    """Return an action that posts a context value as JSON."""

    def action(context: Context) -> None:
        rendered_headers = {"Content-Type": "application/json"}
        rendered_headers.update(_render_mapping(headers or {}, context))
        payload = json.dumps(context[payload_key], default=str).encode("utf-8")
        _open("POST", _render(url, context), data=payload, headers=rendered_headers, timeout=timeout)

    return action


def _open(
    method: str,
    url: str,
    data: Optional[bytes] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 30.0,
) -> bytes:
    req = request.Request(url=url, data=data, headers=headers or {}, method=method)
    with request.urlopen(req, timeout=timeout) as response:
        return response.read()


def _render(value: str, context: Context) -> str:
    return render_template(value, context)


def _render_mapping(values: dict[str, str], context: Context) -> dict[str, str]:
    return {key: _render(value, context) for key, value in values.items()}
