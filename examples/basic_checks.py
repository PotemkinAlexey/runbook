from runbook import Runbook, log, matches_any, not_empty, step

runbook = (
    Runbook("basic checks")
    .add(
        step("Check files")
        .set("files", ["daily.csv"])
        .require(not_empty("files"), "No files found")
        .require(matches_any("files", "*.csv"), "CSV file is missing")
        .then(log("Found {{ files|length }} files"))
    )
)
