# Changelog

## 0.1.0 - 2026-05-09

Initial release.

### Added

- Embeddable `Runbook`, `Stage`, and `Step` execution model.
- Fluent Python DSL with checks, actions, retries, timeouts, skip/warn/fail policies, and explicit `inputs()` / `publish()` contracts.
- `@step` and `@stage` decorator APIs for function-first runbook authoring.
- Nested result tree with JSON serialization, path metadata, failure formatting, and CLI tree output.
- Shared context by default, optional scoped stages, lazy context providers, and parallel expanded item execution.
- Built-in checks and data engineering helpers for file, count, schema, freshness, watermark, manifest, and row-count validation.
- Safe expression evaluator for legacy `expect()` usage.
- Schema validation helpers with callable, Pydantic v1/v2-style, and small JSON-schema-like dict support.
- Declarative JSON/YAML runbook loader backed by built-in checks and Registry checks.
- Extension Registry with explicit Python entry point loading.
- Result exporters, JSONL exporter, and async result exporter.
- CLI commands for validate, list, and run across Python and declarative runbook files.
- Optional integrations for local files, HTTP, and Airflow adapter usage.
- Optional `yaml` extra for declarative YAML files.
- Typed package marker (`py.typed`).
- Documentation site with quickstart, cheat sheet, pipeline guide, examples cookbook, embedding guide, troubleshooting, and project philosophy.

### Notes

- `runbook` is an embeddable local execution layer, not a scheduler or orchestrator.
- Core runtime dependency remains limited to Jinja2.
