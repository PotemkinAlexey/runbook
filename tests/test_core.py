import unittest
from time import sleep

from runbook import Runbook, RunbookFailedError, Step, empty, gt, if_else, matches_any, not_empty, safe_eval, step
from runbook.exceptions import StepExecutionError


class RunbookCoreTest(unittest.TestCase):
    def test_step_applies_loader_and_actions(self):
        context = {}

        def capture(ctx):
            ctx["captured"] = ctx["count"]

        Step("load").with_loader(lambda ctx: 3, "count").expect("count == 3").then(capture).run(context)

        self.assertEqual(context["count"], 3)
        self.assertEqual(context["captured"], 3)

    def test_step_set_and_load_aliases_update_context(self):
        context = {}

        step("aliases").set("base", 2).load("count", lambda ctx: ctx["base"] + 1).run(context)

        self.assertEqual(context["base"], 2)
        self.assertEqual(context["count"], 3)

    def test_step_supports_declarative_requirements(self):
        context = {}

        step("check files").with_data("files", ["daily.csv"]).require(not_empty("files")).require(
            matches_any("files", "*.csv")
        ).run(context)

    def test_requirement_failure_raises_runbook_error(self):
        with self.assertRaises(RunbookFailedError) as raised:
            Step("count").with_data("row_count", 0).require(gt("row_count", 0), "no rows").run({})

        self.assertEqual(raised.exception.condition, "gt(row_count, 0)")

    def test_step_skip_when_skips_actions(self):
        context = {"files": []}

        result = (
            step("skip")
            .skip_when(empty("files"), "nothing to process")
            .then(lambda ctx: ctx.update({"processed": True}))
            .run(context)
        )

        self.assertTrue(result.skipped)
        self.assertEqual(result.message, "nothing to process")
        self.assertNotIn("processed", context)

    def test_step_warn_when_records_warning(self):
        result = step("warn").with_data("delay", 10).warn_when(gt("delay", 5), "late").run({})

        self.assertTrue(result.warned)
        self.assertEqual(result.warnings, ["late"])

    def test_step_fail_when_raises_on_matching_condition(self):
        with self.assertRaises(RunbookFailedError) as raised:
            step("fail").with_data("delay", 10).fail_when(gt("delay", 5), "too late").run({})

        self.assertEqual(raised.exception.message, "too late")

    def test_step_retry_retries_failed_attempts(self):
        context = {"attempts": 0}

        def flaky_loader(ctx):
            ctx["attempts"] += 1
            return ctx["attempts"]

        step("retry").retry(times=2).load("value", flaky_loader).require(gt("value", 1)).run(context)

        self.assertEqual(context["attempts"], 2)

    def test_step_retry_rejects_invalid_attempts(self):
        with self.assertRaises(ValueError):
            step("bad").retry(times=0)

    def test_step_timeout_fails_slow_step(self):
        with self.assertRaises(RunbookFailedError) as raised:
            step("slow").timeout(0.01).then(lambda ctx: sleep(0.05)).run({})

        self.assertEqual(raised.exception.condition, "timeout(0.01)")

    def test_step_timeout_rejects_invalid_seconds(self):
        with self.assertRaises(ValueError):
            step("bad").timeout(0)

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

    def test_runbook_result_serializes_to_dict(self):
        result = Runbook("ok").add(step("load").set("items", [1]).require(not_empty("items"))).execute({})

        data = result.to_dict(include_context=True)

        self.assertEqual(data["status"], "passed")
        self.assertEqual(data["summary"]["passed"], 1)
        self.assertEqual(data["context"]["items"], [1])
        self.assertIsInstance(data["summary"]["duration_seconds"], float)
        self.assertIsInstance(data["steps"][0]["duration_seconds"], float)

    def test_if_else_runs_expected_action(self):
        context = {"ready": True}

        action = if_else(
            "ready",
            lambda ctx: ctx.update({"result": "then"}),
            lambda ctx: ctx.update({"result": "else"}),
        )
        action(context)

        self.assertEqual(context["result"], "then")

    def test_safe_eval_supports_common_safe_expressions(self):
        result = safe_eval("len(files) == 2 and response.status == 200", {
            "files": ["a", "b"],
            "response": {"status": 200},
        })

        self.assertTrue(result)

    def test_safe_eval_blocks_private_attribute_access(self):
        with self.assertRaises(StepExecutionError):
            safe_eval("value.__class__", {"value": "x"})

    def test_safe_eval_blocks_arbitrary_function_calls(self):
        with self.assertRaises(StepExecutionError):
            safe_eval("fn()", {"fn": lambda: True})


if __name__ == "__main__":
    unittest.main()
