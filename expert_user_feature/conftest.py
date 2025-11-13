import os
from typing import Optional, Tuple

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pantau_tular.test_settings")

import django  # noqa: E402
from django.test.utils import (  # noqa: E402
    setup_databases,
    setup_test_environment,
    teardown_databases,
    teardown_test_environment,
)

_db_config: Optional[Tuple] = None


def pytest_configure():
    """
    Ensure Django and the test database are ready before pytest discovers tests.
    This mimics the work done by Django's DiscoverRunner so our pytest-only suite
    can rely on TestCase/TransactionTestCase behaviors (like automatic flushing).
    """

    global _db_config

    django.setup()
    setup_test_environment()
    _db_config = setup_databases(verbosity=0, interactive=False)


def pytest_unconfigure():
    global _db_config

    teardown_databases(_db_config, verbosity=0)
    teardown_test_environment()
    _db_config = None
