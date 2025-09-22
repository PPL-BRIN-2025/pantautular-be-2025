from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from pt_backend.models import Role, User
from django.contrib.auth.hashers import make_password
from pt_backend.models import Disease, Location, Case
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

TEST_API_KEY_HEADER = {"HTTP_X_API_KEY": "test-key"}

@override_settings(SECRET_API_KEYS=("test-key",))
class RolesAndFailedLoginAPITests(TestCase):
    databases = {'default'}

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        # Seed some roles
        Role.objects.create(name='ADMIN')
        Role.objects.create(name='TENAGA_AHLI')
        Role.objects.create(name='VIEWER')

        # Seed a user
        self.user = User.objects.create(
            name='John',
            email='john@example.com',
            password=make_password('StrongP@ss1'),
            role='ADMIN',
        )

    def test_roles_summary(self):
        url = reverse('admin-roles-summary')
        resp = self.client.get(url, **TEST_API_KEY_HEADER)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['count'], 3)
        self.assertListEqual(sorted(data['roles']), ['ADMIN', 'TENAGA_AHLI', 'VIEWER'])

    def test_failed_login_stats_and_logs(self):
        # Trigger failed logins through auth endpoint to exercise flow
        login_url = reverse('login')
        for _ in range(2):
            self.client.post(login_url, {"email": "john@example.com", "password": "wrongpass"}, format='json', **TEST_API_KEY_HEADER)
        # Non-existent email also counts
        self.client.post(login_url, {"email": "noone@example.com", "password": "wrongpass"}, format='json', **TEST_API_KEY_HEADER)

        stats_url = reverse('admin-failed-login-stats')
        resp = self.client.get(stats_url, **TEST_API_KEY_HEADER)
        self.assertEqual(resp.status_code, 200)
        stats = resp.json()
        self.assertGreaterEqual(stats['total_failed'], 3)
        self.assertGreaterEqual(stats['total_unique_emails'], 2)
        self.assertIn('logs_url', stats)

        logs_url = reverse('admin-failed-login-logs')
        resp2 = self.client.get(logs_url, **TEST_API_KEY_HEADER)
        self.assertEqual(resp2.status_code, 200)
        logs = resp2.json()
        self.assertGreaterEqual(logs['count'], 3)
        self.assertTrue(all('email' in ev and 'timestamp' in ev for ev in logs['events']))

    def test_users_summary(self):
        # Add two more users; mark one active via last_login
        u1 = User.objects.create(
            name='Alice',
            email='alice@example.com',
            password=make_password('P@ss1'),
            role='ADMIN',
            last_login=timezone.now(),
        )
        u2 = User.objects.create(
            name='Bob',
            email='bob@example.com',
            password=make_password('P@ss2'),
            role='VIEWER',
        )
        url = reverse('admin-users-summary')
        resp = self.client.get(url, **TEST_API_KEY_HEADER)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Total users: existing seeded 1 + 2 new = 3
        self.assertEqual(data['total_users'], 3)
        # Active users: only Alice (John, Bob have null last_login)
        self.assertEqual(data['active_users'], 1)

    def test_datasets_summary(self):
        # Create minimal dependencies and 3 cases
        disease = Disease.objects.create(name="COVID-19", level_of_alertness=3)
        loc1 = Location.objects.create(latitude=-6.2, longitude=106.8, city="Jakarta", province="DKI Jakarta")
        loc2 = Location.objects.create(latitude=-6.9, longitude=107.6, city="Bandung", province="Jawa Barat")
        Case.objects.create(gender="male", age=30, city="Jakarta", status="minimal", severity="insiden", disease=disease, location=loc1)
        Case.objects.create(gender="female", age=25, city="Bandung", status="biasa", severity="hospitalisasi", disease=disease, location=loc2)
        Case.objects.create(gender="male", age=40, city="Jakarta", status="bahaya", severity="mortalitas", disease=disease, location=loc1)

        url = reverse('admin-datasets-summary')
        resp = self.client.get(url, **TEST_API_KEY_HEADER)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total_datasets'], 3)

    def test_stats_endpoint(self):
        # Seed some additional data
        self.user.last_login = timezone.now()
        self.user.save(update_fields=["last_login"])  # active = 1

        disease = Disease.objects.create(name="COVID-19", level_of_alertness=3)
        loc = Location.objects.create(latitude=-6.2, longitude=106.8, city="Jakarta", province="DKI Jakarta")
        Case.objects.create(gender="male", age=30, city="Jakarta", status="minimal", severity="insiden", disease=disease, location=loc)

        url = reverse('admin-stats')
        resp = self.client.get(url, **TEST_API_KEY_HEADER)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Validate presence and basic correctness
        self.assertIn('totalUsers', data)
        self.assertIn('activeUsers', data)
        self.assertIn('datasets', data)
        self.assertIn('failedLogins', data)
        self.assertIn('roles', data)

        self.assertEqual(data['totalUsers'], User.objects.count())
        self.assertEqual(data['activeUsers'], User.objects.filter(last_login__isnull=False).count())
        self.assertEqual(data['datasets'], Case.objects.count())
        self.assertListEqual(sorted(data['roles']), sorted(list(Role.objects.values_list('name', flat=True))))
        # failedLogins comes from cache, default 0 in a fresh test run
        self.assertIsInstance(data['failedLogins'], int)

    def test_stats_requires_api_key(self):
        url = reverse('admin-stats')
        resp = self.client.get(url)  # no API key
        self.assertEqual(resp.status_code, 401)


@override_settings(SECRET_API_KEYS=("test-key",))
class UsersSummaryMockAndStubTests(TestCase):
    """Unit-style tests using stub and mock to isolate from the database."""

    def setUp(self):
        self.client = APIClient()

    def _url(self):
        return reverse("admin-users-summary")

    def test_users_summary_with_stubbed_counts(self):
        """Stub: provide fixed values without asserting interactions."""

        class _StubQS:
            def count(self):
                return 4  # active users

        class _StubManager:
            def count(self):
                return 10  # total users

            def filter(self, **kwargs):
                # Expect last_login__isnull=False but we don't assert in a stub
                return _StubQS()

        stub_user = SimpleNamespace(objects=_StubManager())

        with patch("admin_feature.views.User", new=stub_user):
            resp = self.client.get(self._url(), **TEST_API_KEY_HEADER)

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total_users"], 10)
        self.assertEqual(body["active_users"], 4)

    def test_users_summary_with_mocks_verifies_calls(self):
        """Mock: verify filter/count calls and arguments."""

        mock_user = SimpleNamespace()
        mock_manager = MagicMock()
        mock_qs = MagicMock()

        mock_manager.count.return_value = 99
        mock_manager.filter.return_value = mock_qs
        mock_qs.count.return_value = 11
        mock_user.objects = mock_manager

        with patch("admin_feature.views.User", new=mock_user):
            resp = self.client.get(self._url(), **TEST_API_KEY_HEADER)

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total_users"], 99)
        self.assertEqual(body["active_users"], 11)

        mock_manager.count.assert_called_once_with()
        mock_manager.filter.assert_called_once_with(last_login__isnull=False)
        mock_qs.count.assert_called_once_with()


@override_settings(SECRET_API_KEYS=("test-key",))
class StatsUsersCountsWithMocksTests(TestCase):
    """Unit-style test for stats endpoint isolating all collaborators."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("admin-stats")

    def test_stats_users_counts_with_mocks(self):
        # Mock User manager and queryset
        mock_user = SimpleNamespace()
        mock_user_manager = MagicMock()
        mock_user_qs = MagicMock()
        mock_user_manager.count.return_value = 7
        mock_user_manager.filter.return_value = mock_user_qs
        mock_user_qs.count.return_value = 3
        mock_user.objects = mock_user_manager

        # Mock Role values_list(...).order_by(...)
        mock_role = SimpleNamespace()
        mock_role_qs = MagicMock()
        mock_role_qs.order_by.return_value = ["ADMIN", "VIEWER"]
        mock_role.values_list = MagicMock(return_value=mock_role_qs)
        mock_role.objects = mock_role

        # Mock datasets service
        mock_datasets_service_class = MagicMock()
        mock_datasets_service_class.return_value.get_total_datasets.return_value = 42

        with patch("admin_feature.views.User", new=mock_user), \
             patch("admin_feature.views.Role", new=mock_role), \
             patch("admin_feature.views.DatasetsService", new=mock_datasets_service_class), \
             patch("admin_feature.views.cache") as mock_cache:
            mock_cache.get.return_value = 5

            resp = self.client.get(self.url, **TEST_API_KEY_HEADER)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["totalUsers"], 7)
        self.assertEqual(data["activeUsers"], 3)
        self.assertEqual(data["datasets"], 42)
        self.assertEqual(data["failedLogins"], 5)
        self.assertEqual(data["roles"], ["ADMIN", "VIEWER"])
