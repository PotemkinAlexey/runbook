import unittest

from runbook import (
    Registry,
    custom,
    get_registered_action,
    get_registered_check,
    list_registered_actions,
    list_registered_checks,
    register_action,
    register_check,
    step,
)


class RegistryTest(unittest.TestCase):
    def test_registry_resolves_check_factory(self):
        registry = Registry()
        registry.register_check("positive", lambda key: custom(f"positive({key})", lambda ctx: ctx[key] > 0))

        result = step("check").set("count", 1).require(registry.check("positive", "count")).run({})

        self.assertTrue(result.passed)
        self.assertEqual(registry.list_checks(), ["positive"])

    def test_registry_resolves_action_factory(self):
        registry = Registry()
        registry.register_action("mark", lambda key: lambda ctx: ctx.update({key: True}))
        context = {}

        step("mark").then(registry.action("mark", "done")).run(context)

        self.assertTrue(context["done"])
        self.assertEqual(registry.list_actions(), ["mark"])

    def test_registry_rejects_duplicate_names(self):
        registry = Registry()
        registry.register_check("ready", lambda: custom("ready", lambda ctx: True))

        with self.assertRaises(ValueError):
            registry.register_check("ready", lambda: custom("ready", lambda ctx: True))

    def test_default_registry_decorator_helpers(self):
        check_name = "test_registry.flag"
        action_name = "test_registry.mark"

        @register_check(check_name, replace=True)
        def flag_check(key):
            return custom(f"flag({key})", lambda ctx: bool(ctx.get(key)))

        @register_action(action_name, replace=True)
        def mark_action(key):
            return lambda ctx: ctx.update({key: True})

        context = {"flag": True}
        step("registered").require(get_registered_check(check_name, "flag")).then(
            get_registered_action(action_name, "done")
        ).run(context)

        self.assertTrue(context["done"])
        self.assertIn(check_name, list_registered_checks())
        self.assertIn(action_name, list_registered_actions())


if __name__ == "__main__":
    unittest.main()
