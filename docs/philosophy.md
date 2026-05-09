# Project Philosophy

`runbook` is an embeddable execution layer, not an orchestrator.

The library should make operational checks, data validation, and small pipeline guardrails easy to describe and easy to embed. It should not own scheduling, workers, deployments, or persistent execution state.

## What runbook Does

`runbook` is responsible for:

- describing a local execution tree
- running steps and stages inside the current Python process
- validating context with checks
- making inputs and outputs explicit
- producing structured results
- formatting readable failures
- exporting final results to application-owned systems
- staying dependency-light and portable

This makes the same runbook usable from a script, CLI command, API endpoint, test, cron job, Airflow task, or another scheduler.

## What runbook Does Not Do

`runbook` should not become responsible for:

- scheduling runs by time or events
- running workers
- managing queues of jobs
- storing run history in a database
- retrying after process restarts
- distributing execution across machines
- managing deployments
- owning secrets, connections, or infrastructure
- replacing Airflow, Dagster, Prefect, cron, CI, or a service runtime

If a feature needs a scheduler, a state backend, or a worker service, it belongs outside core.

## The Boundary

Good fit:

```python
result = runbook.execute(context)
```

The caller decides when to run, where context comes from, what to do with the result, and how to store history.

Poor fit:

```python
runbook.schedule("0 9 * * *").deploy(workers=4)
```

This would turn the library into an orchestrator.

## Design Rules

Keep behavior explicit:

- prefer `inputs()` and `publish()` over hidden data flow
- prefer checks over arbitrary `if/else`
- prefer ordinary Python functions for real I/O
- prefer result exporters over built-in storage backends
- prefer adapters over framework-specific core behavior

Keep advanced features optional:

- `@step` and `@stage` improve Python ergonomics
- declarative JSON/YAML describes wiring and checks
- registry plugins share checks and actions
- async exporters move result delivery off the runbook path

None of these should require users to adopt a framework or service.

## Recommended Product Shape

For most users, the core mental model should stay small:

```python
Runbook("Name")
  .add(stage("Pre-checks")
    .add(step("Find files"))
    .add(step("Check files")))
  .add(step("Run work"))
  .execute(context)
```

Everything else should be a convenience layer around this model.
