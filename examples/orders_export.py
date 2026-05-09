from runbook import (
    JsonlResultExporter,
    Runbook,
    check_row_count,
    check_schema,
    not_empty,
    post_export_checks,
    stage,
    step,
)


def find_files(context):
    return ["orders.csv"]


def read_rows(context):
    return [{"id": 1, "created_at": "2026-05-09T00:00:00Z"}]


def build_manifest(context):
    return {
        "files": context["files"],
        "row_count": context["row_count"],
    }


def build_runbook():
    return (
        Runbook("Orders export")
        .export_to(JsonlResultExporter("runbook-results.jsonl"))
        .add(
            stage("Pre-checks")
            .add(step("Find files").lazy("files", find_files).require(not_empty("files"), "No input files found"))
            .add(
                step("Read rows")
                .inputs("files")
                .publish("rows", read_rows)
                .publish("row_count", lambda context: len(context["rows"]))
            )
            .add(step("Check schema").require(check_schema("rows", ["id", "created_at"])))
            .add(step("Check row count").require(check_row_count("row_count", minimum=1)))
        )
        .add(
            stage("Export").add(
                step("Build manifest")
                .inputs("files", "row_count")
                .publish("manifest", build_manifest)
            )
        )
        .add(post_export_checks())
    )


if __name__ == "__main__":
    result = build_runbook().execute({})
    print(result.to_json(indent=2))
