from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from pt_backend.models import Role, User
from django.contrib.auth.hashers import make_password

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
