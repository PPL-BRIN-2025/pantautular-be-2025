from unittest import TestCase

from authentication.registration import registry
from authentication.registration.base import AbstractRegistrationFactory


class RegistryTests(TestCase):
    def setUp(self):
        self._orig = registry._FACTORIES.copy()
        registry._FACTORIES.clear()

    def tearDown(self):
        # restore original state for other tests
        registry._FACTORIES.clear()
        registry._FACTORIES.update(self._orig)

    # ---------------------------------------------------------------- happy --
    def test_register_and_fetch_factory_case_insensitive(self):
        @registry.register_factory
        class DummyFactory(AbstractRegistrationFactory):
            base_role_name = "TEST_ROLE"

        self.assertIn("TEST_ROLE", registry._FACTORIES)
        self.assertIsInstance(registry._FACTORIES["TEST_ROLE"], DummyFactory)

        fetched = registry.get_factory("test_role")
        self.assertIs(fetched, registry._FACTORIES["TEST_ROLE"])

    # -------------------------------------------------------------- negative --
    def test_get_factory_unknown_role_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            registry.get_factory("NO_SUCH_ROLE")

        # error message lists available keys (empty set here)
        self.assertIn("Available: []", str(ctx.exception))

    # -------------------------------------------------------------- corner  —
    def test_duplicate_role_last_one_wins(self):
        @registry.register_factory
        class FirstFactory(AbstractRegistrationFactory):
            base_role_name = "DUPLICATE"

        first_instance = registry.get_factory("duplicate")

        @registry.register_factory
        class SecondFactory(AbstractRegistrationFactory):
            base_role_name = "DUPLICATE"

        second_instance = registry.get_factory("duplicate")
        self.assertEqual(len(registry._FACTORIES), 1)
        self.assertIsInstance(second_instance, SecondFactory)
        self.assertIsNot(first_instance, second_instance)
