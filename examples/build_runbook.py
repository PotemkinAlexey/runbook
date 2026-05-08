from runbook import Runbook, not_empty, step


def build_runbook():
    return Runbook("factory example").add(
        step("Check items").require(not_empty("items"), "items are required")
    )
