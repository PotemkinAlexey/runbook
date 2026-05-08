"""Reusable actions and context modifiers for runbook steps."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Union

from jinja2 import Template

from .exceptions import RunbookFailedError, StepExecutionError
from .evaluation import safe_eval

Context = Dict[str, Any]
Action = Callable[[Context], Any]


def raise_(msg: str) -> Action:
    """Create an action that fails the current runbook."""

    def action(context: Context) -> None:
        step_name = str(context.get("step_name") or "Manual Step")
        raise RunbookFailedError(step_name, "manual raise_", msg)

    return action


def instant_log(msg: Any, context: Optional[Context] = None) -> None:
    """Render and log a message immediately."""
    try:
        if context and isinstance(msg, str):
            msg = Template(msg).render(context)
    except Exception as exc:  # pragma: no cover - defensive logging path
        msg = f"[log render error] {exc}"
    logging.info(msg)


def log(msg: Union[str, Callable[[Context], Any]]) -> Action:
    """Create an action that logs a rendered message."""

    def action(context: Context) -> None:
        try:
            if callable(msg):
                rendered = msg(context)
            else:
                rendered = Template(msg).render(context)
        except Exception as exc:  # pragma: no cover - defensive logging path
            rendered = f"[log render error] {exc}"
        logging.info(rendered)

    return action


def xcom_push(key: str, value_fn: Callable[[Context], Any]) -> Action:
    """Create an action that pushes a value to Airflow XCom when a task instance exists."""

    def action(context: Context) -> None:
        ti = context.get("ti")
        if not ti:
            logging.warning("No TaskInstance in context, skipping XCom push.")
            return
        value = value_fn(context)
        ti.xcom_push(key=key, value=value)
        logging.info("XCom pushed: %s = %r", key, value)

    return action


def if_(expr: str) -> Callable[[Action], Action]:
    """Wrap an action so it only runs when the expression evaluates to true."""

    def wrapper(action: Action) -> Action:
        def conditional_action(context: Context) -> Any:
            try:
                if safe_eval(expr, context):
                    return action(context)
            except StepExecutionError as exc:
                logging.error(str(exc))
            return None

        return conditional_action

    return wrapper


def if_else(expr: str, then_action: Action, else_action: Action) -> Action:
    """Create an action that runs one of two actions based on an expression."""

    def wrapped(context: Context) -> Any:
        if safe_eval(expr, context):
            return then_action(context)
        return else_action(context)

    return wrapped


def external(key: str, values: Any) -> Callable[[Context], None]:
    """Create a context modifier that injects external values into a context key."""

    def modifier(context: Context) -> None:
        context[key] = values

    return modifier
