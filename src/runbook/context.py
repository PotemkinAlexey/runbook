"""Context helpers."""

from __future__ import annotations

import logging
from typing import Any
from urllib import parse

from .types import Context, Loader


class LazyValue:
    """Context value resolved on first access."""

    def __init__(self, loader: Loader) -> None:
        self.loader = loader
        self.loaded = False
        self.value: Any = None

    def resolve(self, context: Context) -> Any:
        if not self.loaded:
            self.value = self.loader(context)
            self.loaded = True
        return self.value


def lazy(loader: Loader) -> LazyValue:
    return LazyValue(loader)


def resolve_value(value: Any, context: Context) -> Any:
    if isinstance(value, LazyValue):
        return value.resolve(context)
    return value


def resolve_context_value(context: Context, key: str) -> Any:
    value: Any = context
    container: Any = None
    part_for_container: str = ""

    for part in key.split("."):
        value = resolve_value(value, context)
        if isinstance(value, dict):
            container = value
            part_for_container = part
            value = value.get(part)
        else:
            value = getattr(value, part, None)

        if isinstance(value, LazyValue):
            resolved = value.resolve(context)
            if isinstance(container, dict):
                container[part_for_container] = resolved
            value = resolved

        if value is None:
            return None

    return resolve_value(value, context)


def enrich_airflow_context(context: Context) -> Context:
    """Add commonly used Airflow identifiers and a log link to a context dict."""
    try:
        from airflow.models import Variable
    except ImportError as exc:  # pragma: no cover - depends on optional Airflow install
        raise RuntimeError("Airflow is required to enrich an Airflow context.") from exc

    ti = context.get("ti")
    dag_run = context.get("dag_run")
    task = context.get("task") or getattr(ti, "task", None)
    dag = context.get("dag") or getattr(ti, "dag", None)

    context.setdefault("dag_id", getattr(ti, "dag_id", "unknown"))
    context.setdefault("task_id", getattr(ti, "task_id", "unknown"))
    context.setdefault("dag_run_id", getattr(dag_run, "run_id", "manual__unknown"))
    context.setdefault("logical_date", context.get("execution_date"))
    context.setdefault("step_name", context.get("step") or context.get("step_name"))

    if "task" not in context and task:
        context["task"] = task
    if "dag" not in context and dag:
        context["dag"] = dag

    base_url = Variable.get("BASE_URL", default_var="http://localhost:8080")
    if "airflow_link" not in context:
        try:
            context["airflow_link"] = (
                f"{base_url}/dags/{context['dag_id']}/grid"
                f"?dag_run_id={parse.quote(str(context['dag_run_id']))}"
                f"&tab=logs"
                f"&task_id={parse.quote(str(context['task_id']))}"
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            context["airflow_link"] = f"{base_url}/home"
            logging.warning("[enrich_airflow_context] Failed to build link: %s", exc)

    return context
