import unittest

from runbook import Runbook, RunbookFailedError, Step, gt, if_else, matches_any, not_empty, step


class RunbookCoreTest(unittest.TestCase):
    def test_step_applies_loader_and_actions(self):
        context = {}

        def capture(ctx):
            ctx["captured"] = ctx["count"]

        Step("load").with_loader(lambda ctx: 3, "count").expect("count == 3").then(capture).run(context)

        self.assertEqual(context["count"], 3)
        self.assertEqual(context["captured"], 3)

    def test_step_supports_declarative_requirements(self):
        context = {}

        step("check files").with_data("files", ["daily.csv"]).require(not_empty("files")).require(
            matches_any("files", "*.csv")
        ).run(context)

    def test_requirement_failure_raises_runbook_error(self):
        with self.assertRaises(RunbookFailedError) as raised:
            Step("count").with_data("row_count", 0).require(gt("row_count", 0), "no rows").run({})

        self.assertEqual(raised.exception.condition, "gt(row_count, 0)")

    def test_runbook_raises_runbook_error_without_airflow(self):
        runbook = Runbook().add_step(Step("fail").expect("ready", "not ready"))

        with self.assertRaises(RunbookFailedError):
            runbook.run({"ready": False})

    def test_runbook_execute_returns_success_result(self):
        result = Runbook("ok").add(step("load").with_data("ready", True).require(not_empty("ready"))).execute({})

        self.assertTrue(result.passed)
        self.assertFalse(result.failed)
        self.assertEqual(result.name, "ok")
        self.assertEqual([step_result.name for step_result in result.steps], ["load"])
        self.assertIsNone(result.error)

    def test_runbook_execute_returns_failure_result(self):
        result = Runbook("bad").add(step("fail").require(not_empty("files"), "missing files")).execute({})

        self.assertTrue(result.failed)
        self.assertEqual(result.error.condition, "not_empty(files)")
        self.assertEqual(result.steps[-1].status, "failed")

    def test_if_else_runs_expected_action(self):
        context = {"ready": True}

        action = if_else(
            "ready",
            lambda ctx: ctx.update({"result": "then"}),
            lambda ctx: ctx.update({"result": "else"}),
        )
        action(context)

        self.assertEqual(context["result"], "then")


if __name__ == "__main__":
    unittest.main()
