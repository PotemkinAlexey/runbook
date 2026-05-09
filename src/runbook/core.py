"""Core runbook DSL."""

from __future__ import annotations

import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from time import monotonic, sleep
from typing import Any, List, Optional, Union

from .checks import Check
from .context import lazy, resolve_context_value
from .evaluation import safe_eval
from .events import RunbookLogger, get_runbook_logger
from .exceptions import RunbookFailedError, StepExecutionError
from .result import ResultNode, RunbookResult, StageResult, StepResult
from .schema import validate_value
from .templates import render_template
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
        self.required_inputs: List[str] = []
        self.publishers: List[tuple[str, Loader]] = []
        self.schema_validations: List[tuple[str, Any]] = []
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

    def lazy(self, key: str, loader_fn: Loader) -> "Step":
        self.context_modifiers.append(lambda context: context.update({key: lazy(loader_fn)}))
        return self

    def inputs(self, *keys: str) -> "Step":
        self.required_inputs.extend(keys)
        return self

    def publish(self, key: str, fn: Loader) -> "Step":
        self.publishers.append((key, fn))
        return self

    def validate_schema(self, input_key: str, schema: Any) -> "Step":
        self.inputs(input_key)
        self.schema_validations.append((input_key, schema))
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
        self._validate_inputs(context, active_logger)

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
        self._run_schema_validations(context, active_logger)
        warnings = self._run_warning_conditions(context, active_logger)

        for key, publisher in self.publishers:
            context[key] = publisher(context)

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

    def _validate_inputs(self, context: Context, logger: RunbookLogger) -> None:
        for key in self.required_inputs:
            logger.check_started("input", key)
            if _get_context_value(context, key) is None:
                self._fail(context, f"input({key})", f"Missing required input: {key}", logger)

    def _run_schema_validations(self, context: Context, logger: RunbookLogger) -> None:
        for key, schema in self.schema_validations:
            logger.check_started("schema", key)
            try:
                validate_value(_get_context_value(context, key), schema)
            except Exception as exc:
                self._fail(context, f"schema({key})", f"Schema validation failed for {key}: {exc}", logger)

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
            return render_template(message, context)
        except Exception as exc:
            return f"[render error in expect_msg] {exc}"


def step(name: str) -> Step:
    return Step(name)


class Stage:
    """A reusable group of steps and nested stages."""

    def __init__(self, name: str):
        self.name = name
        self.children: List[ExecutableNode] = []
        self.skip_conditions: List[tuple[Check, str]] = []
        self.warning_conditions: List[tuple[Check, str]] = []
        self.failure_conditions: List[tuple[Check, str]] = []
        self.retry_attempts = 1
        self.retry_delay_seconds = 0.0
        self.timeout_seconds: Optional[float] = None
        self.continue_on_error_enabled = False
        self.fail_fast_enabled = True
        self.scoped_context_enabled = False

    def add(self, child: "ExecutableNode") -> "Stage":
        self.children.append(child)
        return self

    def add_step(self, step: Step) -> "Stage":
        return self.add(step)

    def fail_when(self, check: Check, message: str = "Failure condition matched") -> "Stage":
        self.failure_conditions.append((check, message))
        return self

    def skip_when(self, check: Check, message: str = "Skipped") -> "Stage":
        self.skip_conditions.append((check, message))
        return self

    def warn_when(self, check: Check, message: str = "Warning condition matched") -> "Stage":
        self.warning_conditions.append((check, message))
        return self

    def retry(self, times: int, delay: float = 0.0) -> "Stage":
        if times < 1:
            raise ValueError("retry times must be >= 1")
        if delay < 0:
            raise ValueError("retry delay must be >= 0")
        self.retry_attempts = times
        self.retry_delay_seconds = delay
        return self

    def timeout(self, seconds: float) -> "Stage":
        if seconds <= 0:
            raise ValueError("timeout seconds must be > 0")
        self.timeout_seconds = seconds
        return self

    def continue_on_error(self) -> "Stage":
        self.continue_on_error_enabled = True
        self.fail_fast_enabled = False
        return self

    def fail_fast(self) -> "Stage":
        self.fail_fast_enabled = True
        self.continue_on_error_enabled = False
        return self

    def scoped(self, enabled: bool = True) -> "Stage":
        self.scoped_context_enabled = enabled
        return self

    def run(
        self,
        context: Context,
        logger: Optional[RunbookLogger] = None,
        index: Optional[int] = None,
        total: Optional[int] = None,
    ) -> StageResult:
        started_at = monotonic()
        active_logger = logger or get_runbook_logger()
        active_logger.stage_started(self.name, index=index, total=total)

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

    def _run_once(self, context: Context, active_logger: RunbookLogger, started_at: float) -> StageResult:
        stage_context = dict(context) if self.scoped_context_enabled else context
        results: List[ResultNode] = []
        warnings: List[str] = []

        try:
            for check, message in self.skip_conditions:
                active_logger.check_started("stage skip", check.name)
                if _check_matches(self.name, check, stage_context):
                    rendered_msg = render_template(message, stage_context)
                    active_logger.step_skipped(self.name, rendered_msg)
                    return StageResult(
                        name=self.name,
                        status="skipped",
                        message=rendered_msg,
                        duration_seconds=_elapsed(started_at),
                    )

            for check, message in self.failure_conditions:
                active_logger.check_started("stage fail_when", check.name)
                if _check_matches(self.name, check, stage_context):
                    raise RunbookFailedError(self.name, check.name, render_template(message, stage_context))

            for check, message in self.warning_conditions:
                active_logger.check_started("stage warn_when", check.name)
                if _check_matches(self.name, check, stage_context):
                    rendered_msg = render_template(message, stage_context)
                    active_logger.step_warning(self.name, rendered_msg)
                    warnings.append(rendered_msg)

            had_child_failure = False
            for child_index, child in enumerate(self.children, start=1):
                try:
                    results.append(
                        child.run(stage_context, logger=active_logger, index=child_index, total=len(self.children))
                    )
                except RunbookFailedError as exc:
                    had_child_failure = True
                    failed_result = _failed_result_from_error(exc, started_at)
                    if not _result_already_recorded(results, failed_result):
                        results.append(failed_result)
                    if self.fail_fast_enabled:
                        raise

            if had_child_failure:
                return StageResult(
                    name=self.name,
                    status="failed",
                    children=results,
                    warnings=warnings,
                    duration_seconds=_elapsed(started_at),
                )

            active_logger.stage_passed(self.name)
            return StageResult.success(
                self.name,
                results,
                warnings=warnings,
                duration_seconds=_elapsed(started_at),
            )
        except RunbookFailedError as exc:
            active_logger.stage_failed(self.name, exc.condition)
            failed_result = _failed_result_from_error(exc, started_at)
            if not _result_already_recorded(results, failed_result):
                results.append(failed_result)
            stage_result = StageResult.failure(
                self.name,
                results,
                exc,
                warnings=warnings,
                duration_seconds=_elapsed(started_at),
            )
            exc.result = stage_result
            exc.path = [self.name] + list(getattr(exc, "path", [exc.step_name]))
            raise


def stage(name: str) -> Stage:
    return Stage(name)


ExecutableNode = Union[Step, Stage]


class Runbook:
    """A sequence of runbook steps."""

    def __init__(self, name: Optional[str] = None):
        self.name = name
        self.steps: List[ExecutableNode] = []
        self.on_failure: Optional[Action] = None
        self.expander_key: Optional[str] = None
        self.expander_steps: List[Step] = []
        self.expander_parallel = False
        self.expander_max_workers: Optional[int] = None
        self.in_expand_mode = False

    def notify_on_failure(self, fn: Action) -> "Runbook":
        self.on_failure = fn
        return self

    def add_step(self, step: Step) -> "Runbook":
        return self.add(step)

    def add(self, child: ExecutableNode) -> "Runbook":
        if self.in_expand_mode:
            if not isinstance(child, Step):
                raise TypeError("expand() can only contain Step instances")
            self.expander_steps.append(child)
        else:
            self.steps.append(child)
        return self

    def expand(
        self,
        key: str,
        parallel: bool = False,
        max_workers: Optional[int] = None,
    ) -> "Expansion":
        if self.in_expand_mode:
            raise RuntimeError("nested expand() is not supported")
        self.expander_key = key
        self.expander_parallel = parallel
        self.expander_max_workers = max_workers
        self.in_expand_mode = True
        return Expansion(self)

    def end_expand(self) -> "Runbook":
        if not self.in_expand_mode:
            raise RuntimeError("end_expand() called without expand()")

        steps_to_run = list(self.expander_steps)
        expander_key = self.expander_key
        parallel = self.expander_parallel
        max_workers = self.expander_max_workers

        def run_expander(context: Context) -> None:
            logger = get_runbook_logger()
            items = context.get(expander_key, [])
            if not items:
                logger.expand_empty(expander_key)
                return

            logger.expand_started(expander_key, len(items))
            if parallel:
                _run_expanded_items_parallel(items, context, steps_to_run, logger, max_workers)
                return

            for item in items:
                _run_expanded_item(item, context, steps_to_run, logger)

        wrapper_step = Step(f"Expand[{expander_key}]").then(run_expander)
        self.steps.append(wrapper_step)

        self.expander_key = None
        self.expander_steps = []
        self.expander_parallel = False
        self.expander_max_workers = None
        self.in_expand_mode = False
        return self

    def _discard_expand(self) -> None:
        self.expander_key = None
        self.expander_steps = []
        self.expander_parallel = False
        self.expander_max_workers = None
        self.in_expand_mode = False

    def execute(self, context: Context) -> RunbookResult:
        started_at = monotonic()
        children: List[ResultNode] = []
        logger = get_runbook_logger()
        logger.runbook_started(self.name, len(self.steps))

        try:
            for index, child in enumerate(self.steps, start=1):
                child_result = child.run(context, logger=logger, index=index, total=len(self.steps))
                children.append(child_result)
                if child_result.failed:
                    error = RunbookFailedError(child_result.name, "failed", child_result.message or "Child failed")
                    logger.runbook_failed(self.name, error.step_name, error.condition)
                    self._run_failure_handler(context, logger)
                    return RunbookResult.failure(
                        self.name,
                        context,
                        error,
                        children=children,
                        duration_seconds=_elapsed(started_at),
                    )
            logger.runbook_passed(self.name, len(children))
            return RunbookResult.success(self.name, context, children=children, duration_seconds=_elapsed(started_at))
        except RunbookFailedError as exc:
            logger.runbook_failed(self.name, exc.step_name, exc.condition)
            failed_result = _failed_result_from_error(exc, started_at)
            if not _result_already_recorded(children, failed_result):
                children.append(failed_result)
            self._run_failure_handler(context, logger)
            return RunbookResult.failure(
                self.name,
                context,
                exc,
                children=children,
                duration_seconds=_elapsed(started_at),
            )

    def execute_parallel(self, context: Context, max_workers: Optional[int] = None) -> RunbookResult:
        started_at = monotonic()
        logger = get_runbook_logger()
        logger.runbook_started(self.name, len(self.steps))
        results_by_index: dict[int, ResultNode] = {}
        contexts_by_index: dict[int, Context] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_run_step_in_context_copy, step, context, index, len(self.steps), logger): index
                for index, step in enumerate(self.steps, start=1)
            }

            for future in as_completed(futures):
                index = futures[future]
                try:
                    child_result, step_context = future.result()
                except RunbookFailedError as exc:
                    logger.runbook_failed(self.name, exc.step_name, exc.condition)
                    failed_children = _ordered_results(results_by_index)
                    failed_result = _failed_result_from_error(exc, started_at)
                    if not _result_already_recorded(failed_children, failed_result):
                        failed_children.append(failed_result)
                    self._run_failure_handler(context, logger)
                    return RunbookResult.failure(
                        self.name,
                        context,
                        exc,
                        children=failed_children,
                        duration_seconds=_elapsed(started_at),
                    )

                results_by_index[index] = child_result
                contexts_by_index[index] = step_context

        for index in sorted(contexts_by_index):
            context.update(contexts_by_index[index])

        children = _ordered_results(results_by_index)
        logger.runbook_passed(self.name, len(children))
        return RunbookResult.success(self.name, context, children=children, duration_seconds=_elapsed(started_at))

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


class Expansion:
    """Context manager for defining expanded steps."""

    def __init__(self, runbook: Runbook):
        self.runbook = runbook

    def __enter__(self) -> "Expansion":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            self.runbook._discard_expand()
            return False
        self.runbook.end_expand()
        return False

    def add_step(self, step: Step) -> "Expansion":
        self.runbook.add_step(step)
        return self

    def add(self, step: Step) -> "Expansion":
        return self.add_step(step)

    def end_expand(self) -> Runbook:
        return self.runbook.end_expand()


def _elapsed(started_at: float) -> float:
    return round(monotonic() - started_at, 6)


def _run_step_in_context_copy(
    step: ExecutableNode,
    context: Context,
    index: int,
    total: int,
    logger: RunbookLogger,
) -> tuple[ResultNode, Context]:
    step_context = context.copy()
    return step.run(step_context, logger=logger, index=index, total=total), step_context


def _ordered_results(results_by_index: dict[int, ResultNode]) -> List[ResultNode]:
    return [results_by_index[index] for index in sorted(results_by_index)]


def _failed_result_from_error(error: RunbookFailedError, started_at: float) -> ResultNode:
    result = getattr(error, "result", None)
    if isinstance(result, (StepResult, StageResult)):
        return result
    return StepResult(name=error.step_name, status="failed", duration_seconds=_elapsed(started_at))


def _check_matches(name: str, check: Check, context: Context) -> bool:
    try:
        return check(context)
    except Exception as exc:
        raise RunbookFailedError(name, check.name, f"Check failed with error: {exc}") from None


def _result_already_recorded(results: List[ResultNode], failed_result: ResultNode) -> bool:
    return any(result is failed_result for result in results)


def _get_context_value(context: Context, key: str) -> Any:
    return resolve_context_value(context, key)


def _run_expanded_item(item: Any, context: Context, steps_to_run: List[Step], logger: RunbookLogger) -> None:
    sub_context = context.copy()
    sub_context["item"] = item
    for step in steps_to_run:
        step.run(sub_context, logger=logger)


def _run_expanded_items_parallel(
    items: list[Any],
    context: Context,
    steps_to_run: List[Step],
    logger: RunbookLogger,
    max_workers: Optional[int],
) -> None:
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_run_expanded_item, item, context, steps_to_run, logger)
            for item in items
        ]
        for future in as_completed(futures):
            future.result()


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
