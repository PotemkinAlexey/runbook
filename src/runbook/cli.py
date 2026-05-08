"""Command line interface for running runbooks."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Optional

from .core import Runbook


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="runbook")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a runbook file")
    run_parser.add_argument("file", help="Python file that defines a runbook")
    run_parser.add_argument("--context", default="{}", help="JSON object used as the initial context")

    validate_parser = subparsers.add_parser("validate", help="Validate that a runbook file can be loaded")
    validate_parser.add_argument("file", help="Python file that defines a runbook")

    list_parser = subparsers.add_parser("list", help="List steps in a runbook file")
    list_parser.add_argument("file", help="Python file that defines a runbook")

    args = parser.parse_args(argv)

    if args.command == "validate":
        load_runbook_from_file(args.file)
        print("valid")
        return 0

    runbook = load_runbook_from_file(args.file)

    if args.command == "list":
        for step in runbook.steps:
            print(step.name)
        return 0

    if args.command == "run":
        context = _parse_context(args.context)
        result = runbook.execute(context)
        if result.passed:
            print("passed")
            return 0
        print(result.error, file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


def load_runbook_from_file(path: str) -> Runbook:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"runbook file not found: {file_path}")

    module_name = f"_runbook_cli_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load runbook file: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    candidate = _find_runbook_candidate(module)
    if not isinstance(candidate, Runbook):
        raise TypeError("runbook file must define `runbook`, `checks`, or `build_runbook()`")
    return candidate


def _find_runbook_candidate(module: Any) -> Any:
    for attr in ("runbook", "checks"):
        if hasattr(module, attr):
            return getattr(module, attr)
    if hasattr(module, "build_runbook"):
        return module.build_runbook()
    return None


def _parse_context(raw_context: str) -> dict[str, Any]:
    try:
        value = json.loads(raw_context)
    except json.JSONDecodeError as exc:
        raise ValueError(f"context must be a JSON object: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("context must be a JSON object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
