"""Notification actions for runbooks."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from .context import enrich_airflow_context
from .templates import render_template
from .types import Context


def slack_notify(
    conn_id: str,
    channel: str,
    title: str,
    message: str,
    context_info: Optional[Dict[str, Any]] = None,
):
    """Create an action that sends a Slack message through an Airflow connection."""

    def action(context: Context) -> None:
        try:
            from airflow.hooks.base import BaseHook
            from slack_sdk import WebClient
            from slack_sdk.errors import SlackApiError
        except ImportError as exc:
            logging.error("Slack notification dependencies are missing: %s", exc)
            return

        context = enrich_airflow_context(context)
        conn = BaseHook.get_connection(conn_id)
        token = conn.password or conn.extra_dejson.get("token")
        client = WebClient(token=token)

        rendered_title = _render_template(title, context, "Slack title")
        rendered_message = _render_template(message, context, "Slack message")
        text = _build_slack_message(rendered_title, rendered_message, context, context_info)

        try:
            client.chat_postMessage(channel=channel, text=text)
        except SlackApiError as exc:
            logging.error("Slack SDK error: %s", exc.response.get("error"))
        except Exception as exc:
            logging.error("Slack SDK exception: %s", exc)

    return action


def email_notify(
    smtp_server: str,
    port: int,
    login: str,
    password: str,
    from_addr: str,
    to_addrs: List[str],
    subject: str,
    body: str,
):
    """Create an action that sends an email through SMTP over SSL."""

    def action(context: Context) -> None:
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_addrs)

            with smtplib.SMTP_SSL(smtp_server, port) as server:
                server.login(login, password)
                server.sendmail(from_addr, to_addrs, msg.as_string())
        except Exception as exc:
            logging.error("Email notification failed: %s", exc)

    return action


def email_notify_ses(email_data: Dict[str, Any], conn_id: str = "aws_default"):
    """Create an action that sends an email through AWS SES v2 via Airflow."""

    def action(context: Context) -> None:
        try:
            from email.mime.application import MIMEApplication
            from email.mime.multipart import MIMEMultipart

            from airflow.providers.amazon.aws.hooks.ses import SesHook

            ses_hook = SesHook(aws_conn_id=conn_id)
            msg = MIMEMultipart()
            msg["Subject"] = email_data["subject"]
            msg["From"] = email_data["mail_from"]
            msg["To"] = ", ".join(email_data["to"])
            if email_data.get("cc"):
                msg["Cc"] = ", ".join(email_data["cc"])
            if email_data.get("bcc"):
                msg["Bcc"] = ", ".join(email_data["bcc"])
            if email_data.get("reply_to"):
                msg["Reply-To"] = email_data["reply_to"]

            msg.attach(MIMEText(email_data["html_content"], "html"))

            for path in email_data.get("files", []):
                with open(path, "rb") as file_obj:
                    part = MIMEApplication(file_obj.read())
                    part.add_header("Content-Disposition", "attachment", filename=os.path.basename(path))
                    msg.attach(part)

            ses_hook.send_raw_email(
                raw_data=msg.as_string(),
                source=email_data["mail_from"],
                to_addresses=email_data["to"],
                cc_addresses=email_data.get("cc", []),
                bcc_addresses=email_data.get("bcc", []),
            )
        except Exception as exc:
            logging.error("SES email failed: %s", exc)

    return action


def _render_template(template: str, context: Context, label: str) -> str:
    try:
        return render_template(template, context)
    except Exception as exc:
        logging.warning("[%s] Failed to render: %s", label, exc)
        return template


def _build_slack_message(
    rendered_title: str,
    rendered_message: str,
    context: Context,
    context_info: Optional[Dict[str, Any]],
) -> str:
    execution_date = context.get("logical_date")
    execution_date_str = str(execution_date) if execution_date else "unknown"
    step_name = context.get("step_name", "unknown")

    text = f":rotating_light: *{rendered_title}*\n{rendered_message}\n\n"
    text += f"*DAG*: `{context.get('dag_id', 'unknown')}`\n"
    text += f"*Task*: `{context.get('task_id', 'unknown')}`\n"
    text += f"*Execution*: `{execution_date_str}`\n"
    text += f"<{context.get('airflow_link')}|View in Airflow>\n"

    if context_info or step_name:
        text += "\n*Extra context:*\n"
        if step_name:
            text += f"*Step*: {step_name}\n"
        for key, value in (context_info or {}).items():
            value_str = str(value)
            if len(value_str) > 1000:
                value_str = value_str[:997] + "..."
            text += f"*{key}*: {value_str}\n"

    return text
