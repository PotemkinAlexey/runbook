# runbook

Small Python library for describing Airflow-oriented operational runbooks.

## Install locally

```bash
pip install -e .
```

## Basic usage

```python
from runbook import Runbook, Step, log

runbook = (
    Runbook()
    .add_step(
        Step("Check files")
        .with_data("files", ["daily.csv"])
        .expect("len(files) > 0", "No files found")
        .then(log("Found {{ files|length }} files"))
    )
)

runbook.run({})
```

The base package only depends on Jinja2. Airflow, Slack, AWS, Azure, Snowflake, and SFTP integrations are imported lazily when the corresponding action or loader is used.

## License

MIT
