"""Build runbooks from declarative dictionaries and files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .checks import (
    all_of,
    any_of,
    contains,
    custom,
    empty,
    equals,
    exists,
    gt,
    gte,
    lt,
    lte,
    matches_any,
    missing,
    not_,
    not_empty,
)
from .core import Runbook, Stage, Step, stage, step
from .data import (
    check_files_exist,
    check_freshness,
    check_manifest_exists,
    check_not_empty,
    check_row_count,
    check_schema,
    check_watermark,
    compare_row_counts,
)
from .registry import Registry, default_registry

CheckFactoryMap = Dict[str, Any]

BUILTIN_CHECKS: CheckFactoryMap = {
    "all_of": all_of,
    "any_of": any_of,
    "contains": contains,
    "custom": custom,
    "empty": empty,
    "equals": equals,
    "exists": exists,
    "gt": gt,
    "gte": gte,
    "lt": lt,
    "lte": lte,
    "matches_any": matches_any,
    "missing": missing,
    "not_": not_,
    "not_empty": not_empty,
    "check_files_exist": check_files_exist,
    "check_freshness": check_freshness,
    "check_manifest_exists": check_manifest_exists,
    "check_not_empty": check_not_empty,
    "check_row_count": check_row_count,
    "check_schema": check_schema,
    "check_watermark": check_watermark,
    "compare_row_counts": compare_row_counts,
}


def runbook_from_dict(spec: dict[str, Any], registry: Optional[Registry] = None) -> Runbook:
    """Build a Runbook from a declarative dictionary."""

    _require_mapping(spec, "runbook spec")
    runbook = Runbook(spec.get("name"))
    for child_spec in _child_specs(spec):
        runbook.add(_node_from_dict(child_spec, registry or default_registry))
    return runbook


def runbook_from_file(path: str, registry: Optional[Registry] = None) -> Runbook:
    """Build a Runbook from a JSON or YAML file."""

    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"runbook file not found: {file_path}")
    return runbook_from_dict(_load_spec_file(file_path), registry=registry)


def _node_from_dict(spec: dict[str, Any], registry: Registry) -> Any:
    _require_mapping(spec, "node spec")
    if _is_stage_spec(spec):
        return _stage_from_dict(spec, registry)
    return _step_from_dict(spec, registry)


def _stage_from_dict(spec: dict[str, Any], registry: Registry) -> Stage:
    item = stage(_required_name(spec, "stage"))
    _apply_common_controls(item, spec, registry)
    if spec.get("continue_on_error"):
        item.continue_on_error()
    if spec.get("fail_fast"):
        item.fail_fast()
    if spec.get("scoped"):
        item.scoped()
    for child_spec in _child_specs(spec):
        item.add(_node_from_dict(child_spec, registry))
    return item


def _step_from_dict(spec: dict[str, Any], registry: Registry) -> Step:
    item = step(_required_name(spec, "step"))
    _apply_common_controls(item, spec, registry)
    inputs = spec.get("inputs") or []
    if inputs:
        item.inputs(*_as_list(inputs, "inputs"))
    for requirement in _as_list(spec.get("require") or [], "require"):
        check, message = _check_from_spec(requirement, registry)
        item.require(check, message)
    for schema_spec in _as_list(spec.get("validate_schema") or [], "validate_schema"):
        _require_mapping(schema_spec, "validate_schema")
        key = schema_spec.get("key")
        if not key:
            raise ValueError("validate_schema spec must include `key`")
        if "schema" not in schema_spec:
            raise ValueError("validate_schema spec must include `schema`")
        item.validate_schema(key, schema_spec["schema"])
    return item


def _apply_common_controls(item: Any, spec: dict[str, Any], registry: Registry) -> None:
    if "retry" in spec:
        retry_spec = spec["retry"]
        if isinstance(retry_spec, int):
            item.retry(times=retry_spec)
        else:
            _require_mapping(retry_spec, "retry")
            item.retry(times=retry_spec.get("times", 1), delay=retry_spec.get("delay", 0.0))
    if "timeout" in spec:
        item.timeout(spec["timeout"])
    for check_spec in _as_list(spec.get("skip_when") or [], "skip_when"):
        check, message = _check_from_spec(check_spec, registry, default_message="Skipped")
        item.skip_when(check, message)
    for check_spec in _as_list(spec.get("warn_when") or [], "warn_when"):
        check, message = _check_from_spec(check_spec, registry, default_message="Warning condition matched")
        item.warn_when(check, message)
    for check_spec in _as_list(spec.get("fail_when") or [], "fail_when"):
        check, message = _check_from_spec(check_spec, registry, default_message="Failure condition matched")
        item.fail_when(check, message)


def _check_from_spec(spec: Any, registry: Registry, default_message: str = "Requirement failed"):
    if isinstance(spec, str):
        return _build_check(spec, [], {}, registry), default_message
    _require_mapping(spec, "check spec")
    name = spec.get("check")
    if not name:
        raise ValueError("check spec must include `check`")
    args = _as_list(spec.get("args") or [], "args")
    kwargs = {
        key: value
        for key, value in spec.items()
        if key not in {"check", "args", "message"}
    }
    message = spec.get("message", default_message)
    return _build_check(name, args, kwargs, registry), message


def _build_check(name: str, args: list[Any], kwargs: dict[str, Any], registry: Registry):
    if name in BUILTIN_CHECKS:
        return BUILTIN_CHECKS[name](*args, **kwargs)
    return registry.check(name, *args, **kwargs)


def _child_specs(spec: dict[str, Any]) -> Iterable[dict[str, Any]]:
    if "children" in spec:
        return _as_list(spec["children"], "children")
    return [*_as_list(spec.get("stages") or [], "stages"), *_as_list(spec.get("steps") or [], "steps")]


def _is_stage_spec(spec: dict[str, Any]) -> bool:
    if spec.get("type") == "stage":
        return True
    return any(key in spec for key in ("children", "stages", "steps"))


def _required_name(spec: dict[str, Any], kind: str) -> str:
    name = spec.get("name")
    if not name:
        raise ValueError(f"{kind} spec must include `name`")
    return name


def _require_mapping(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a mapping")


def _as_list(value: Any, label: str) -> list[Any]:
    if isinstance(value, list):
        return value
    raise TypeError(f"{label} must be a list")


def _load_spec_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    if suffix in {".yaml", ".yml"}:
        return _load_yaml(path)
    raise ValueError(f"unsupported declarative runbook file type: {path.suffix}")


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError("YAML runbooks require PyYAML to be installed.") from exc
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)
