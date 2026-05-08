"""Airflow integration helpers.

The core runbook package does not depend on Airflow. Use these helpers only
inside Airflow tasks or DAG code.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from jinja2 import Template

from runbook.context import enrich_airflow_context
from runbook.exceptions import RunbookFailedError
from runbook.notifications import email_notify_ses, slack_notify
from runbook.types import Context

__all__ = [
    "azure_blobs",
    "email_notify_ses",
    "enrich_airflow_context",
    "ftp_files",
    "run_task",
    "s3_keys",
    "sftp_files",
    "slack_notify",
    "snowflake_count",
    "xcom_push",
]


def run_task(runbook, context: Context) -> None:
    """Run a runbook and convert failures to AirflowFailException."""
    try:
        runbook.run(context)
    except RunbookFailedError as exc:
        from airflow.exceptions import AirflowFailException

        raise AirflowFailException(str(exc)) from None


def sftp_files(conn_id: str, path: str):
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

    return loader


def ftp_files(conn_id: str, path: str):
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

    return loader


def azure_blobs(conn_id: str, container: str, prefix: str):
    def loader(context: Context) -> List[str]:
        from airflow.providers.microsoft.azure.hooks.wasb import WasbHook

        hook = WasbHook(conn_id)
        resolved_prefix = Template(prefix).render(context)
        return hook.get_blobs_list(container, prefix=resolved_prefix)

    return loader


def s3_keys(conn_id: str, bucket: str, prefix: str):
    def loader(context: Context) -> Optional[List[str]]:
        from airflow.providers.amazon.aws.hooks.s3 import S3Hook

        hook = S3Hook(aws_conn_id=conn_id)
        resolved_prefix = Template(prefix).render(context)
        return hook.list_keys(bucket, prefix=resolved_prefix)

    return loader


def snowflake_count(sql: str, conn_id: str):
    def loader(context: Context) -> int:
        from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook

        rendered_sql = Template(sql).render(context)
        hook = SnowflakeHook(conn_id)
        records = hook.get_records(rendered_sql)
        return len(records)

    return loader


def xcom_push(key: str, value_fn):
    def action(context: Context) -> None:
        ti = context.get("ti")
        if ti is None:
            logging.warning("[xcom_push] No 'ti' in context, skipping key=%s", key)
            return

        value = value_fn(context)
        ti.xcom_push(key=key, value=value)
        logging.info("XCom pushed: %s = %r", key, value)

    return action
