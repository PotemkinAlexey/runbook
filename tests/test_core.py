import unittest

from runbook import Runbook, RunbookFailedError, Step, if_else


class RunbookCoreTest(unittest.TestCase):
    def test_step_applies_loader_and_actions(self):
        context = {}

        def capture(ctx):
            ctx["captured"] = ctx["count"]

        Step("load").with_loader(lambda ctx: 3, "count").expect("count == 3").then(capture).run(context)

        self.assertEqual(context["count"], 3)
        self.assertEqual(context["captured"], 3)

    def test_runbook_raises_runbook_error_without_airflow(self):
        runbook = Runbook().add_step(Step("fail").expect("ready", "not ready"))

        with self.assertRaises(RunbookFailedError):
            runbook.run({"ready": False})

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
