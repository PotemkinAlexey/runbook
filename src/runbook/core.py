"""Core runbook DSL."""

from __future__ import annotations

import signal
from contextlib import contextmanager
from time import monotonic, sleep
from typing import Any, Callable, List, Optional

from jinja2 import Template

from .checks import Check
from .evaluation import safe_eval
from .events import RunbookLogger, get_runbook_logger
from .exceptions import RunbookFailedError, StepExecutionError
from .result import RunbookResult, StepResult
from .types import Action, Context, ContextModifier, Loader


class Step:
    """A single check or action group in a runbook."""

    def __init__(self, name: str):
        self.name = name
        self.expect_expr: Optional[str] = None
        self.expect_msg = ""
        self.requirements: List[tuple[Check, str]] = []
        self.skip_conditions: List[tuple[Check, str]] = []
        self.warning_conditions: List[tuple[Check, str]] = []
        self.failure_conditions: List[tuple[Check, str]] = []
        self.context_modifiers: List[ContextModifier] = []
        self.actions: List[Action] = []
        self.on_expect_failure: List[Action] = []
        self.retry_attempts = 1
        self.retry_delay_seconds = 0.0
        self.timeout_seconds: Optional[float] = None
        self._logger = get_runbook_logger()

    def expect(self, expr: str, message: str = "Expectation failed") -> "Step":
        self.expect_expr = expr
        self.expect_msg = message
        return self

    def require(self, check: Check, message: str = "Requirement failed") -> "Step":
        self.requirements.append((check, message))
        return self

    def fail_when(self, check: Check, message: str = "Failure condition matched") -> "Step":
        self.failure_conditions.append((check, message))
        return self

    def skip_when(self, check: Check, message: str = "Skipped") -> "Step":
        self.skip_conditions.append((check, message))
        return self

    def warn_when(self, check: Check, message: str = "Warning condition matched") -> "Step":
        self.warning_conditions.append((check, message))
        return self

    def retry(self, times: int, delay: float = 0.0) -> "Step":
        if times < 1:
            raise ValueError("retry times must be >= 1")
        if delay < 0:
            raise ValueError("retry delay must be >= 0")
        self.retry_attempts = times
        self.retry_delay_seconds = delay
        return self

    def timeout(self, seconds: float) -> "Step":
        if seconds <= 0:
            raise ValueError("timeout seconds must be > 0")
        self.timeout_seconds = seconds
        return self

    def with_data(self, key: str, value: Any) -> "Step":
        self.context_modifiers.append(lambda context: context.update({key: value}))
        return self

    def set(self, key: str, value: Any) -> "Step":
        return self.with_data(key, value)

    def with_loader(self, loader_fn: Loader, key: str) -> "Step":
        self.context_modifiers.append(lambda context: context.update({key: loader_fn(context)}))
        return self

    def load(self, key: str, loader_fn: Loader) -> "Step":
        return self.with_loader(loader_fn, key)

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
                    self._logger.xcom_pushed(key, value)
                else:
                    self._logger.xcom_skipped(key)
            except Exception as exc:
                self._logger.xcom_failed(key, exc)

        self.actions.append(action)
        return self

    def run(
        self,
        context: Context,
        logger: Optional[RunbookLogger] = None,
        index: Optional[int] = None,
        total: Optional[int] = None,
    ) -> StepResult:
        started_at = monotonic()
        active_logger = logger or self._logger
        active_logger.step_started(self.name, index=index, total=total)

        for attempt in range(1, self.retry_attempts + 1):
            try:
                with _step_timeout(self.timeout_seconds, self.name):
                    return self._run_once(context, active_logger, started_at)
            except RunbookFailedError as exc:
                if attempt >= self.retry_attempts:
                    raise
                active_logger.step_retry(self.name, attempt + 1, self.retry_attempts, exc.condition)
                if self.retry_delay_seconds:
                    sleep(self.retry_delay_seconds)

        raise RuntimeError("unreachable retry state")

    def _run_once(self, context: Context, active_logger: RunbookLogger, started_at: float) -> StepResult:
        for modifier in self.context_modifiers:
            modifier(context)

        skip_result = self._run_skip_conditions(context, active_logger)
        if skip_result:
            active_logger.step_skipped(self.name, skip_result.message)
            return StepResult(
                name=skip_result.name,
                status=skip_result.status,
                message=skip_result.message,
                warnings=skip_result.warnings,
                duration_seconds=_elapsed(started_at),
            )

        self._run_expression_expectation(context, active_logger)
        self._run_failure_conditions(context, active_logger)
        self._run_requirements(context, active_logger)
        warnings = self._run_warning_conditions(context, active_logger)

        for action in self.actions:
            action(context)

        active_logger.step_passed(self.name)
        return StepResult(name=self.name, warnings=warnings, duration_seconds=_elapsed(started_at))

    def _run_skip_conditions(self, context: Context, logger: RunbookLogger) -> Optional[StepResult]:
        for check, message in self.skip_conditions:
            logger.check_started("skip", check.name)
            if self._check_matches(check, context):
                rendered_msg = self._render_message(message, context)
                return StepResult(name=self.name, status="skipped", message=rendered_msg)
        return None

    def _run_expression_expectation(self, context: Context, logger: RunbookLogger) -> None:
        if not self.expect_expr:
            return

        logger.check_started("expect", self.expect_expr)
        try:
            result = safe_eval(self.expect_expr, context)
        except StepExecutionError as exc:
            raise RunbookFailedError(self.name, self.expect_expr, f"Evaluation failed: {exc}") from None

        if not result:
            self._fail(context, self.expect_expr, self.expect_msg, logger)

    def _run_failure_conditions(self, context: Context, logger: RunbookLogger) -> None:
        for check, message in self.failure_conditions:
            logger.check_started("fail_when", check.name)
            if self._check_matches(check, context):
                self._fail(context, check.name, message, logger)

    def _run_requirements(self, context: Context, logger: RunbookLogger) -> None:
        for check, message in self.requirements:
            logger.check_started("require", check.name)
            if not self._check_matches(check, context):
                self._fail(context, check.name, message, logger)

    def _run_warning_conditions(self, context: Context, logger: RunbookLogger) -> List[str]:
        warnings: List[str] = []
        for check, message in self.warning_conditions:
            logger.check_started("warn_when", check.name)
            if self._check_matches(check, context):
                rendered_msg = self._render_message(message, context)
                logger.step_warning(self.name, rendered_msg)
                warnings.append(rendered_msg)
        return warnings

    def _check_matches(self, check: Check, context: Context) -> bool:
        try:
            return check(context)
        except Exception as exc:
            raise RunbookFailedError(self.name, check.name, f"Check failed with error: {exc}") from None

    def _fail(self, context: Context, condition: str, message: str, logger: RunbookLogger) -> None:
        context["step_name"] = self.name
        rendered_msg = self._render_message(message, context)
        logger.step_failed(self.name, condition)

        for notify_fn in self.on_expect_failure:
            try:
                notify_fn(context)
            except Exception as exc:
                logger.handler_failed("notify_on_failure", exc)

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
            logger = get_runbook_logger()
            items = context.get(expander_key, [])
            if not items:
                logger.expand_empty(expander_key)
                return

            logger.expand_started(expander_key, len(items))
            for item in items:
                sub_context = context.copy()
                sub_context["item"] = item
                for step in steps_to_run:
                    step.run(sub_context, logger=logger)

        wrapper_step = Step(f"Expand[{expander_key}]").then(run_expander)
        self.steps.append(wrapper_step)

        self.expander_key = None
        self.expander_steps = []
        self.in_expand_mode = False
        return self

    def execute(self, context: Context) -> RunbookResult:
        started_at = monotonic()
        executed_steps: List[StepResult] = []
        logger = get_runbook_logger()
        logger.runbook_started(self.name, len(self.steps))

        try:
            for index, step in enumerate(self.steps, start=1):
                executed_steps.append(step.run(context, logger=logger, index=index, total=len(self.steps)))
            logger.runbook_passed(self.name, len(executed_steps))
            return RunbookResult.success(self.name, context, executed_steps, duration_seconds=_elapsed(started_at))
        except RunbookFailedError as exc:
            logger.runbook_failed(self.name, exc.step_name, exc.condition)
            executed_steps.append(
                StepResult(name=exc.step_name, status="failed", duration_seconds=_elapsed(started_at))
            )
            self._run_failure_handler(context, logger)
            return RunbookResult.failure(self.name, context, executed_steps, exc, duration_seconds=_elapsed(started_at))

    def run(self, context: Context) -> None:
        result = self.execute(context)
        if result.failed and result.error:
            raise result.error from None

    def _run_failure_handler(self, context: Context, logger: RunbookLogger) -> None:
        if not self.on_failure:
            return
        try:
            self.on_failure(context)
        except Exception as exc:
            logger.handler_failed("runbook notify_on_failure", exc)


def _elapsed(started_at: float) -> float:
    return round(monotonic() - started_at, 6)


@contextmanager
def _step_timeout(seconds: Optional[float], step_name: str):
    if seconds is None:
        yield
        return

    if not hasattr(signal, "setitimer"):
        raise RuntimeError("step timeout is not supported on this platform")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)

    def handle_timeout(signum, frame):
        raise TimeoutError(f"step timed out after {seconds} seconds")

    signal.signal(signal.SIGALRM, handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    except TimeoutError as exc:
        raise RunbookFailedError(step_name, f"timeout({seconds})", str(exc)) from None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])
        signal.signal(signal.SIGALRM, previous_handler)
