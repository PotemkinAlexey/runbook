"""Data engineering checks and stage factories."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from .checks import Check
from .core import Stage, stage, step


def check_files_exist(key: str = "files") -> Check:
    return Check(f"check_files_exist({key})", lambda context: all(Path(path).exists() for path in context.get(key, [])))


def check_not_empty(key: str) -> Check:
    return Check(f"check_not_empty({key})", lambda context: bool(context.get(key)))


def check_row_count(key: str = "row_count", minimum: int = 1) -> Check:
    return Check(f"check_row_count({key}, minimum={minimum})", lambda context: context.get(key, 0) >= minimum)


def check_schema(key: str, required_fields: Iterable[str]) -> Check:
    fields = tuple(required_fields)

    def predicate(context):
        value = context.get(key)
        if isinstance(value, dict):
            return all(field in value for field in fields)
        if isinstance(value, list):
            return all(isinstance(item, dict) and all(field in item for field in fields) for item in value)
        return False

    return Check(f"check_schema({key})", predicate)


def check_freshness(key: str, max_age_seconds: float, now_key: Optional[str] = None) -> Check:
    def predicate(context):
        value = _to_datetime(context.get(key))
        now = _to_datetime(context.get(now_key)) if now_key else datetime.now(timezone.utc)
        if value is None or now is None:
            return False
        return now - value <= timedelta(seconds=max_age_seconds)

    return Check(f"check_freshness({key}, max_age_seconds={max_age_seconds})", predicate)


def check_watermark(key: str, minimum_key: str) -> Check:
    return Check(
        f"check_watermark({key}, minimum={minimum_key})",
        lambda context: context.get(key) >= context.get(minimum_key),
    )


def check_manifest_exists(key: str = "manifest") -> Check:
    return Check(f"check_manifest_exists({key})", lambda context: bool(context.get(key)))


def compare_row_counts(left_key: str, right_key: str, tolerance: int = 0) -> Check:
    def predicate(context):
        left = context.get(left_key)
        right = context.get(right_key)
        if left is None or right is None:
            return False
        return abs(left - right) <= tolerance

    return Check(f"compare_row_counts({left_key}, {right_key}, tolerance={tolerance})", predicate)


def pre_export_checks(files_key: str = "files", schema_key: Optional[str] = None, required_fields=None) -> Stage:
    checks = stage("Pre-export checks").add(
        step("Check files").inputs(files_key).require(check_not_empty(files_key), "No input files found")
    )
    if schema_key and required_fields:
        checks.add(step("Check schema").inputs(schema_key).require(check_schema(schema_key, required_fields)))
    return checks


def export_stage(name: str = "Export", action=None) -> Stage:
    export = stage(name)
    run_export = step("Run export")
    if action is not None:
        run_export.then(action)
    export.add(run_export)
    return export


def post_export_checks(manifest_key: str = "manifest") -> Stage:
    return stage("Post-export checks").add(
        step("Validate manifest")
        .inputs(manifest_key)
        .require(check_manifest_exists(manifest_key), "Manifest is missing")
    )


def validation_stage(name: str = "Validation", *checks: Check) -> Stage:
    validation = stage(name)
    for check in checks:
        validation.add(step(check.name).require(check))
    return validation


def _to_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None
