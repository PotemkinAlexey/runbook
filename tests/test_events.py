import io
import logging
import unittest

from runbook import Runbook, gt, step
from runbook.events import RUNBOOK_LOGGER_NAME


class RunbookEventsTest(unittest.TestCase):
    def test_runbook_logs_step_lifecycle(self):
        stream = io.StringIO()
        logger = logging.getLogger(RUNBOOK_LOGGER_NAME)
        previous_handlers = list(logger.handlers)
        previous_level = logger.level
        previous_propagate = logger.propagate
        logger.handlers = []
        logger.setLevel(logging.INFO)
        logger.propagate = False

        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        self.addCleanup(self._restore_logger, logger, previous_handlers, previous_level, previous_propagate)

        Runbook("logging").add(step("Check count").set("count", 2).require(gt("count", 1))).run({})

        output = stream.getvalue()
        self.assertIn("runbook | start: logging (1 steps)", output)
        self.assertIn("runbook | step 1/1 start: Check count", output)
        self.assertIn("runbook | check require: gt(count, 1)", output)
        self.assertIn("runbook | step pass: Check count", output)
        self.assertIn("runbook | pass: logging (1 steps)", output)

    def _restore_logger(self, logger, handlers, level, propagate):
        logger.handlers = handlers
        logger.setLevel(level)
        logger.propagate = propagate


if __name__ == "__main__":
    unittest.main()
