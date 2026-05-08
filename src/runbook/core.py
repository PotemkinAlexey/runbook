"""Core runbook DSL."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from jinja2 import Template

from .checks import Check
from .exceptions import RunbookFailedError, StepExecutionError
from .evaluation import safe_eval

Context = Dict[str, Any]
Action = Callable[[Context], Any]
ContextModifier = Callable[[Context], Any]


class Step:
    """A single check or action group in a runbook."""

    def __init__(self, name: str):
        self.name = name
        self.expect_expr: Optional[str] = None
        self.expect_msg = ""
        self.requirements: List[tuple[Check, str]] = []
        self.context_modifiers: List[ContextModifier] = []
        self.actions: List[Action] = []
        self.on_expect_failure: List[Action] = []

    def expect(self, expr: str, message: str = "Expectation failed") -> "Step":
        self.expect_expr = expr
        self.expect_msg = message
        return self

    def require(self, check: Check, message: str = "Requirement failed") -> "Step":
        self.requirements.append((check, message))
        return self

    def with_data(self, key: str, value: Any) -> "Step":
        self.context_modifiers.append(lambda context: context.update({key: value}))
        return self

    def with_loader(self, loader_fn: Callable[[Context], Any], key: str) -> "Step":
        self.context_modifiers.append(lambda context: context.update({key: loader_fn(context)}))
        return self

    def with_external(self, modifier_fn: ContextModifier) -> "Step":
        self.context_modifiers.append(modifier_fn)
        return self

    def then(self, *actions: Action) -> "Step":
        self.actions.extend(actions)
        return self

    def notify_on_failure(self, *notify_fns: Action) -> "Step":
        """Register actions that run when this step's expectation fails."""
        self.on_expect_failure.extend(notify_fns)
        return self

    def xcom_push(self, key: str, value_fn: Callable[[Context], Any]) -> "Step":
        def action(context: Context) -> None:
            try:
                value = value_fn(context)
                ti = context.get("ti")
                if ti is not None:
                    ti.xcom_push(key=key, value=value)
                    logging.info("XCom pushed: %s = %r", key, value)
                else:
                    logging.warning("[xcom_push] No 'ti' in context, skipping key=%s", key)
            except Exception as exc:
                logging.error("[xcom_push] Failed to push key=%s: %s", key, exc)

        self.actions.append(action)
        return self

    def run(self, context: Context) -> None:
        logging.info("Step: %s", self.name)

        for modifier in self.context_modifiers:
            modifier(context)

        self._run_expression_expectation(context)
        self._run_requirements(context)

        for action in self.actions:
            action(context)

    def _run_expression_expectation(self, context: Context) -> None:
        if not self.expect_expr:
            return

        logging.info("Evaluating: %s", self.expect_expr)
        try:
            result = safe_eval(self.expect_expr, context)
        except StepExecutionError as exc:
            raise RunbookFailedError(self.name, self.expect_expr, f"Evaluation failed: {exc}") from None

        if not result:
            self._fail(context, self.expect_expr, self.expect_msg)

    def _run_requirements(self, context: Context) -> None:
        for check, message in self.requirements:
            logging.info("Checking: %s", check.name)
            try:
                result = check(context)
            except Exception as exc:
                raise RunbookFailedError(self.name, check.name, f"Check failed with error: {exc}") from None

            if not result:
                self._fail(context, check.name, message)

    def _fail(self, context: Context, condition: str, message: str) -> None:
        context["step_name"] = self.name
        rendered_msg = self._render_message(message, context)

        for notify_fn in self.on_expect_failure:
            try:
                notify_fn(context)
            except Exception as exc:
                logging.error("[notify_on_failure] Failed to run notifier: %s", exc)

        raise RunbookFailedError(self.name, condition, rendered_msg)

    def _render_expect_message(self, context: Context) -> str:
        return self._render_message(self.expect_msg, context)

    def _render_message(self, message: str, context: Context) -> str:
        try:
            return Template(message).render(context)
        except Exception as exc:
            return f"[render error in expect_msg] {exc}"


def step(name: str) -> Step:
    return Step(name)


class Runbook:
    """A sequence of runbook steps."""

    def __init__(self, name: Optional[str] = None):
        self.name = name
        self.steps: List[Step] = []
        self.on_failure: Optional[Action] = None
        self.expander_key: Optional[str] = None
        self.expander_steps: List[Step] = []
        self.in_expand_mode = False

    def notify_on_failure(self, fn: Action) -> "Runbook":
        self.on_failure = fn
        return self

    def add_step(self, step: Step) -> "Runbook":
        if self.in_expand_mode:
            self.expander_steps.append(step)
        else:
            self.steps.append(step)
        return self

    def add(self, step: Step) -> "Runbook":
        return self.add_step(step)

    def expand(self, key: str) -> "Runbook":
        self.expander_key = key
        self.in_expand_mode = True
        return self

    def end_expand(self) -> "Runbook":
        if not self.in_expand_mode:
            raise RuntimeError("end_expand() called without expand()")

        steps_to_run = list(self.expander_steps)
        expander_key = self.expander_key

        def run_expander(context: Context) -> None:
            items = context.get(expander_key, [])
            if not items:
                logging.info("[expand] No items for %s, skipping.", expander_key)
                return

            logging.info("[expand] Iterating over %s items from key=%s", len(items), expander_key)
            for item in items:
                sub_context = context.copy()
                sub_context["item"] = item
                for step in steps_to_run:
                    step.run(sub_context)

        wrapper_step = Step(f"Expand[{expander_key}]").then(run_expander)
        self.steps.append(wrapper_step)

        self.expander_key = None
        self.expander_steps = []
        self.in_expand_mode = False
        return self

    def run(self, context: Context) -> None:
        try:
            logging.info("Starting Runbook%s", f": {self.name}" if self.name else "")
            for step in self.steps:
                step.run(context)
            logging.info("Runbook completed successfully")
        except RunbookFailedError as exc:
            logging.error(str(exc))
            self._run_failure_handler(context)
            raise exc from None

    def _run_failure_handler(self, context: Context) -> None:
        if not self.on_failure:
            return
        try:
            self.on_failure(context)
        except Exception as exc:
            logging.error("[runbook notify_on_failure] Failed to run handler: %s", exc)
