"""Core runbook DSL."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from jinja2 import Template

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
        self.context_modifiers: List[ContextModifier] = []
        self.actions: List[Action] = []
        self.on_expect_failure: List[Action] = []

    def expect(self, expr: str, message: str = "Expectation failed") -> "Step":
        self.expect_expr = expr
        self.expect_msg = message
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

        if self.expect_expr:
            logging.info("Evaluating: %s", self.expect_expr)
            try:
                result = safe_eval(self.expect_expr, context)
            except StepExecutionError as exc:
                raise RunbookFailedError(self.name, self.expect_expr, f"Evaluation failed: {exc}") from None

            if not result:
                context["step_name"] = self.name
                rendered_msg = self._render_expect_message(context)

                for notify_fn in self.on_expect_failure:
                    try:
                        notify_fn(context)
                    except Exception as exc:
                        logging.error("[notify_on_failure] Failed to run notifier: %s", exc)

                raise RunbookFailedError(self.name, self.expect_expr, rendered_msg)

        for action in self.actions:
            action(context)

    def sftp(self, conn_id: str, path: str, key: str = "ftp_files") -> "Step":
        def loader(context: Context) -> List[str]:
            import paramiko
            from airflow.hooks.base import BaseHook

            conn = BaseHook.get_connection(conn_id)
            resolved_path = Template(path).render(context)
            transport = paramiko.Transport((conn.host, 22))
            try:
                transport.connect(username=conn.login, password=conn.password)
                sftp = paramiko.SFTPClient.from_transport(transport)
                try:
                    sftp.chdir(resolved_path)
                    return sftp.listdir(path=".")
                finally:
                    sftp.close()
            finally:
                transport.close()

        return self.with_loader(loader, key)

    def ftp(self, conn_id: str, path: str, key: str = "ftp_files") -> "Step":
        def loader(context: Context) -> List[str]:
            from ftplib import FTP_TLS

            from airflow.hooks.base import BaseHook

            conn = BaseHook.get_connection(conn_id)
            resolved_path = Template(path).render(context)
            ftp = FTP_TLS(host=conn.host, user=conn.login, passwd=conn.password)
            try:
                ftp.prot_p()
                ftp.cwd(resolved_path)
                return ftp.nlst()
            finally:
                ftp.quit()

        return self.with_loader(loader, key)

    def azure(self, conn_id: str, container: str, prefix: str, key: str = "azure_files") -> "Step":
        def loader(context: Context) -> List[str]:
            from airflow.providers.microsoft.azure.hooks.wasb import WasbHook

            hook = WasbHook(conn_id)
            resolved_prefix = Template(prefix).render(context)
            return hook.get_blobs_list(container, prefix=resolved_prefix)

        return self.with_loader(loader, key)

    def s3(self, conn_id: str, bucket: str, prefix: str, key: str = "s3_files") -> "Step":
        def loader(context: Context) -> Optional[List[str]]:
            from airflow.providers.amazon.aws.hooks.s3 import S3Hook

            hook = S3Hook(aws_conn_id=conn_id)
            resolved_prefix = Template(prefix).render(context)
            return hook.list_keys(bucket, prefix=resolved_prefix)

        return self.with_loader(loader, key)

    def snowflake_query(self, sql: str, conn_id: str, key: str = "query_count") -> "Step":
        def loader(context: Context) -> int:
            from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook

            rendered_sql = Template(sql).render(context)
            hook = SnowflakeHook(conn_id)
            records = hook.get_records(rendered_sql)
            return len(records)

        return self.with_loader(loader, key)

    def _render_expect_message(self, context: Context) -> str:
        try:
            return Template(self.expect_msg).render(context)
        except Exception as exc:
            return f"[render error in expect_msg] {exc}"


class Runbook:
    """A sequence of runbook steps."""

    def __init__(self):
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
            logging.info("Starting Runbook")
            for step in self.steps:
                step.run(context)
            logging.info("Runbook completed successfully")
        except RunbookFailedError as exc:
            logging.error(str(exc))
            self._run_failure_handler(context)
            _raise_airflow_fail_exception(exc)

    def _run_failure_handler(self, context: Context) -> None:
        if not self.on_failure:
            return
        try:
            self.on_failure(context)
        except Exception as exc:
            logging.error("[runbook notify_on_failure] Failed to run handler: %s", exc)


def _raise_airflow_fail_exception(error: RunbookFailedError) -> None:
    try:
        from airflow.exceptions import AirflowFailException
    except ImportError:
        raise error from None
    raise AirflowFailException(str(error)) from None
