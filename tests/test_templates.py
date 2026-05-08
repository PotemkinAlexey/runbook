import unittest

from runbook.templates import _compile_template, render_template


class TemplatesTest(unittest.TestCase):
    def test_render_template_reuses_compiled_template(self):
        _compile_template.cache_clear()

        self.assertEqual(render_template("hello {{ name }}", {"name": "Alex"}), "hello Alex")
        self.assertEqual(render_template("hello {{ name }}", {"name": "Runbook"}), "hello Runbook")

        self.assertEqual(_compile_template.cache_info().hits, 1)


if __name__ == "__main__":
    unittest.main()
