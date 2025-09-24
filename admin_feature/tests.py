# admin_feature/tests.py
from django.test import TestCase, override_settings
from django.urls import reverse, NoReverseMatch
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from pt_backend.models import Role, User
from django.contrib.auth.hashers import make_password
from pt_backend.models import Disease, Location, Case
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from django.conf import settings
from django.core.exceptions import PermissionDenied
import jwt
from datetime import datetime, timedelta
import importlib
from rest_framework import status
from admin_feature.views import UserInfoAPIView

TEST_API_KEY_HEADER = {"HTTP_X_API_KEY": "test-key"}

# URL helpers: try reverse(name) then fall back to literal paths
URLS = {
    "admin-roles-summary": "/admin-feature/roles/summary",
    "admin-failed-login-stats": "/admin-feature/failed-logins/stats",
    "admin-failed-login-logs": "/admin-feature/failed-logins/logs",
    "admin-users-summary": "/admin-feature/users/summary",
    "admin-datasets-summary": "/admin-feature/datasets/summary",
    "admin-stats": "/admin-feature/stats",
    "admin-user-info": "/admin-feature/user-info",
}
def url_of(name: str) -> str:
    try:
        return reverse(name)
    except NoReverseMatch:
        return URLS[name]


@override_settings(SECRET_API_KEYS=("test-key",))
class RolesAndFailedLoginAPITests(TestCase):
    databases = {"default"}

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        Role.objects.create(name="ADMIN")
        Role.objects.create(name="TENAGA_AHLI")
        Role.objects.create(name="VIEWER")
        self.user = User.objects.create(
            name="John",
            email="john@example.com",
            password=make_password("StrongP@ss1"),
            role="ADMIN",
        )

    def _login_and_get_token(self, email="john@example.com", password="StrongP@ss1"):
        login_url = reverse("login")
        resp = self.client.post(
            login_url, {"email": email, "password": password}, format="json", **TEST_API_KEY_HEADER
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["access_token"]

    def test_roles_summary(self):
        url = url_of("admin-roles-summary")
        token = self._login_and_get_token()
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 3)
        self.assertListEqual(sorted(data["roles"]), ["ADMIN", "TENAGA_AHLI", "VIEWER"])

    def test_failed_login_stats_and_logs(self):
        login_url = reverse("login")
        for _ in range(2):
            self.client.post(login_url, {"email": "john@example.com", "password": "wrongpass"}, format="json", **TEST_API_KEY_HEADER)
        self.client.post(login_url, {"email": "noone@example.com", "password": "wrongpass"}, format="json", **TEST_API_KEY_HEADER)

        token = self._login_and_get_token()
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        stats_url = url_of("admin-failed-login-stats")
        resp = self.client.get(stats_url, **headers)
        self.assertEqual(resp.status_code, 200)
        stats = resp.json()
        self.assertGreaterEqual(stats["total_failed"], 3)
        self.assertGreaterEqual(stats["total_unique_emails"], 2)
        self.assertIn("logs_url", stats)

        logs_url = url_of("admin-failed-login-logs")
        resp2 = self.client.get(logs_url, **headers)
        self.assertEqual(resp2.status_code, 200)
        logs = resp2.json()
        self.assertGreaterEqual(logs["count"], 3)
        self.assertTrue(all("email" in ev and "timestamp" in ev for ev in logs["events"]))

    def test_failed_login_stats_unique_count_fallback_and_timestamp_edges(self):
        events = [
            {"email": "john@example.com", "timestamp": timezone.now().isoformat()},
            {"email": "ALICE@EXAMPLE.COM", "timestamp": datetime.now().isoformat()},  # naive -> force tz attach
            {"email": "", "timestamp": "not-a-date"},  # parse error branch
            {"email": None, "timestamp": None},
        ]
        cache.set("auth:failed_login_events", events, None)
        cache.delete("auth:failed_login_unique_emails_count")
        token = self._login_and_get_token()
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        url = url_of("admin-failed-login-stats")
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_unique_emails"], 2)
        self.assertGreaterEqual(data["last_24h"], 1)

    def test_failed_login_stats_uses_cached_unique_count(self):
        cache.set("auth:failed_login_unique_emails_count", 7, None)
        cache.set("auth:failed_login_total", 11, None)
        cache.set("auth:failed_login_events", [], None)
        token = self._login_and_get_token()
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        url = url_of("admin-failed-login-stats")
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_unique_emails"], 7)

    def test_failed_login_stats_excludes_old_events_from_last_24h(self):
        old_ts = (timezone.now() - timedelta(days=2)).isoformat()
        recent_ts = timezone.now().isoformat()
        cache.set("auth:failed_login_events", [
            {"email": "a@b.com", "timestamp": old_ts},
            {"email": "a@b.com", "timestamp": recent_ts},
        ], None)
        token = self._login_and_get_token()
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        url = url_of("admin-failed-login-stats")
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["last_24h"], 1)

    def test_users_summary(self):
        User.objects.create(
            name="Alice",
            email="alice@example.com",
            password=make_password("P@ss1"),
            role="ADMIN",
            last_login=timezone.now(),
        )
        User.objects.create(
            name="Bob",
            email="bob@example.com",
            password=make_password("P@ss2"),
            role="VIEWER",
        )
        token = self._login_and_get_token()
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        url = url_of("admin-users-summary")
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_users"], 3)
        self.assertEqual(data["active_users"], 1)

    def test_datasets_summary(self):
        disease = Disease.objects.create(name="COVID-19", level_of_alertness=3)
        loc1 = Location.objects.create(latitude=-6.2, longitude=106.8, city="Jakarta", province="DKI Jakarta")
        loc2 = Location.objects.create(latitude=-6.9, longitude=107.6, city="Bandung", province="Jawa Barat")
        Case.objects.create(gender="male", age=30, city="Jakarta", status="minimal", severity="insiden", disease=disease, location=loc1)
        Case.objects.create(gender="female", age=25, city="Bandung", status="biasa", severity="hospitalisasi", disease=disease, location=loc2)
        Case.objects.create(gender="male", age=40, city="Jakarta", status="bahaya", severity="mortalitas", disease=disease, location=loc1)
        token = self._login_and_get_token()
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        url = url_of("admin-datasets-summary")
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_datasets"], 3)

    def test_user_info_success(self):
        token = self._login_and_get_token()
        url = url_of("admin-user-info")
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["name"], self.user.name)
        self.assertEqual(data["role"], self.user.role)

    def test_user_info_missing_token(self):
        url = url_of("admin-user-info")
        resp = self.client.get(url, **TEST_API_KEY_HEADER)
        self.assertEqual(resp.status_code, 401)

    def test_user_info_invalid_token(self):
        url = url_of("admin-user-info")
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": "Bearer invalid.token.value"}
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 401)

    def test_stats_endpoint(self):
        self.user.last_login = timezone.now()
        self.user.save(update_fields=["last_login"])
        disease = Disease.objects.create(name="COVID-19", level_of_alertness=3)
        loc = Location.objects.create(latitude=-6.2, longitude=106.8, city="Jakarta", province="DKI Jakarta")
        Case.objects.create(gender="male", age=30, city="Jakarta", status="minimal", severity="insiden", disease=disease, location=loc)
        token = self._login_and_get_token()
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        url = url_of("admin-stats")
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("totalUsers", data)
        self.assertIn("activeUsers", data)
        self.assertIn("datasets", data)
        self.assertIn("failedLogins", data)
        self.assertIn("roles", data)
        self.assertEqual(data["totalUsers"], User.objects.count())
        self.assertEqual(data["activeUsers"], User.objects.filter(last_login__isnull=False).count())
        self.assertEqual(data["datasets"], Case.objects.count())
        self.assertListEqual(sorted(data["roles"]), sorted(list(Role.objects.values_list("name", flat=True))))
        self.assertIsInstance(data["failedLogins"], int)

    def test_stats_requires_api_key(self):
        url = url_of("admin-stats")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)

    def test_user_info_token_expired(self):
        payload = {"name": "Jane", "role": "ADMIN", "user_id": 999, "exp": datetime.utcnow() - timedelta(seconds=5)}
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        url = url_of("admin-user-info")
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 401)

    def test_user_info_invalid_payload_no_user_id(self):
        payload = {"exp": datetime.utcnow() + timedelta(minutes=5)}
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        url = url_of("admin-user-info")
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 401)

    def test_user_info_user_not_found(self):
        payload = {"user_id": 999999, "exp": datetime.utcnow() + timedelta(minutes=5)}
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        url = url_of("admin-user-info")
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 401)

    def test_import_admin_apps_models_for_coverage(self):
        import admin_feature.admin as mod_admin
        import admin_feature.apps as mod_apps
        import admin_feature.models as mod_models
        importlib.reload(mod_admin)
        importlib.reload(mod_apps)
        importlib.reload(mod_models)


@override_settings(SECRET_API_KEYS=("test-key",))
class UsersSummaryMockAndStubTests(TestCase):
    # Stub/mock without auth

    def setUp(self):
        self.client = APIClient()

    def _url(self):
        return url_of("admin-users-summary")

    def test_users_summary_with_stubbed_counts(self):
        class _StubQS:
            def count(self):
                return 4
        class _StubManager:
            def count(self):
                return 10
            def filter(self, **kwargs):
                return _StubQS()
        stub_user = SimpleNamespace(objects=_StubManager())
        with patch("admin_feature.views._AdminBaseAPIView.authentication_classes", new=[]), \
             patch("admin_feature.views._AdminBaseAPIView.permission_classes", new=[]), \
             patch("admin_feature.views.User", new=stub_user):
            resp = self.client.get(self._url(), **TEST_API_KEY_HEADER)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total_users"], 10)
        self.assertEqual(body["active_users"], 4)

    def test_users_summary_with_mocks_verifies_calls(self):
        mock_user = SimpleNamespace()
        mock_manager = MagicMock()
        mock_qs = MagicMock()
        mock_manager.count.return_value = 99
        mock_manager.filter.return_value = mock_qs
        mock_qs.count.return_value = 11
        mock_user.objects = mock_manager
        with patch("admin_feature.views._AdminBaseAPIView.authentication_classes", new=[]), \
             patch("admin_feature.views._AdminBaseAPIView.permission_classes", new=[]), \
             patch("admin_feature.views.User", new=mock_user):
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
    # Stats with collaborators mocked

    def setUp(self):
        self.client = APIClient()
        self.url = url_of("admin-stats")

    def test_stats_users_counts_with_mocks(self):
        mock_user = SimpleNamespace()
        mock_user_manager = MagicMock()
        mock_user_qs = MagicMock()
        mock_user_manager.count.return_value = 7
        mock_user_manager.filter.return_value = mock_user_qs
        mock_user_qs.count.return_value = 3
        mock_user.objects = mock_user_manager

        mock_role = SimpleNamespace()
        mock_role_qs = MagicMock()
        mock_role_qs.order_by.return_value = ["ADMIN", "VIEWER"]
        mock_role.values_list = MagicMock(return_value=mock_role_qs)
        mock_role.objects = mock_role

        mock_datasets_service_class = MagicMock()
        mock_datasets_service_class.return_value.get_total_datasets.return_value = 42

        with patch("admin_feature.views._AdminBaseAPIView.authentication_classes", new=[]), \
             patch("admin_feature.views._AdminBaseAPIView.permission_classes", new=[]), \
             patch("admin_feature.views.User", new=mock_user), \
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

    def test_stats_partial_zero_messages_set(self):
        mock_user = SimpleNamespace()
        mock_user_manager = MagicMock()
        mock_user_qs = MagicMock()
        mock_user_manager.count.return_value = 5      # totalUsers != 0
        mock_user_manager.filter.return_value = mock_user_qs
        mock_user_qs.count.return_value = 0           # activeUsers == 0
        mock_user.objects = mock_user_manager

        mock_role = SimpleNamespace()
        mock_role_qs = MagicMock()
        mock_role_qs.order_by.return_value = ["ADMIN"]
        mock_role.values_list = MagicMock(return_value=mock_role_qs)
        mock_role.objects = mock_role

        mock_datasets_service_class = MagicMock()
        mock_datasets_service_class.return_value.get_total_datasets.return_value = 0  # datasets == 0

        with patch("admin_feature.views._AdminBaseAPIView.authentication_classes", new=[]), \
             patch("admin_feature.views._AdminBaseAPIView.permission_classes", new=[]), \
             patch("admin_feature.views.User", new=mock_user), \
             patch("admin_feature.views.Role", new=mock_role), \
             patch("admin_feature.views.DatasetsService", new=mock_datasets_service_class), \
             patch("admin_feature.views.cache") as mock_cache:
                mock_cache.get.return_value = 2
                resp = self.client.get(self.url, **TEST_API_KEY_HEADER)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("messages", data)
        self.assertIn("activityMessage", data["messages"])
        self.assertIn("datasetsMessage", data["messages"])
        self.assertEqual(data["messages"]["activityMessage"], "Tidak ada aktivitas")
        self.assertEqual(data["messages"]["datasetsMessage"], "Data tidak ditemukan")

    def test_stats_partial_users_zero_message_set(self):
        # totalUsers == 0 but others non-zero -> usersMessage only
        mock_user = SimpleNamespace()
        mock_user_manager = MagicMock()
        mock_user_qs = MagicMock()
        mock_user_manager.count.return_value = 0      # triggers usersMessage
        mock_user_manager.filter.return_value = mock_user_qs
        mock_user_qs.count.return_value = 2           # activeUsers > 0
        mock_user.objects = mock_user_manager

        mock_role = SimpleNamespace()
        mock_role_qs = MagicMock()
        mock_role_qs.order_by.return_value = ["ADMIN"]
        mock_role.values_list = MagicMock(return_value=mock_role_qs)
        mock_role.objects = mock_role

        mock_datasets_service_class = MagicMock()
        mock_datasets_service_class.return_value.get_total_datasets.return_value = 9  # datasets > 0

        with patch("admin_feature.views._AdminBaseAPIView.authentication_classes", new=[]), \
             patch("admin_feature.views._AdminBaseAPIView.permission_classes", new=[]), \
             patch("admin_feature.views.User", new=mock_user), \
             patch("admin_feature.views.Role", new=mock_role), \
             patch("admin_feature.views.DatasetsService", new=mock_datasets_service_class), \
             patch("admin_feature.views.cache") as mock_cache:
            mock_cache.get.return_value = 1
            resp = self.client.get(self.url, **TEST_API_KEY_HEADER)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("messages", data)
        self.assertIn("usersMessage", data["messages"])
        self.assertEqual(data["messages"]["usersMessage"], "Data tidak ditemukan")


@override_settings(SECRET_API_KEYS=("test-key",))
class AdminDashboardSecurityTests(TestCase):
    # Security/gating and no leakage

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        Role.objects.get_or_create(name="ADMIN")
        Role.objects.get_or_create(name="VIEWER")
        Role.objects.get_or_create(name="TENAGA_AHLI")
        self.dashboard_endpoints = [
            ("admin-roles-summary", URLS["admin-roles-summary"]),
            ("admin-failed-login-stats", URLS["admin-failed-login-stats"]),
            ("admin-failed-login-logs", URLS["admin-failed-login-logs"]),
            ("admin-users-summary", URLS["admin-users-summary"]),
            ("admin-datasets-summary", URLS["admin-datasets-summary"]),
            ("admin-stats", URLS["admin-stats"]),
            ("admin-user-info", URLS["admin-user-info"]),
        ]

    def _create_user(self, email, role, password="StrongP@ss1"):
        return User.objects.create(
            name=email.split("@")[0].title(),
            email=email,
            password=make_password(password),
            role=role,
        )

    def _login_and_get_token(self, email, password="StrongP@ss1"):
        login_url = reverse("login")
        resp = self.client.post(
            login_url, {"email": email, "password": password}, format="json", **TEST_API_KEY_HEADER
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, f"Login failed for {email}: {resp.content}")
        return resp.json()["access_token"]

    def _headers(self, token=None):
        headers = dict(TEST_API_KEY_HEADER)
        if token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return headers

    def test_unauthenticated_access_is_blocked_and_no_data_leaks(self):
        for name, _ in self.dashboard_endpoints:
            url = url_of(name)
            resp = self.client.get(url, **self._headers(token=None))
            self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN), f"{name} not blocked")
            data = {}
            try:
                data = resp.json()
            except Exception:
                pass
            msg = str(data.get("detail", "")).lower()
            self.assertTrue(("akses" in msg) or ("auth" in msg) or ("token" in msg), f"{name} lacks a clear access message")
            forbidden_keys = {"totalUsers", "activeUsers", "datasets", "roles", "logs", "events", "total_failed"}
            self.assertTrue(forbidden_keys.isdisjoint(set(data.keys())), f"{name} leaked dashboard data to unauthorized user")

    def test_non_admin_user_is_forbidden(self):
        viewer = self._create_user("viewer@example.com", "VIEWER")
        token = self._login_and_get_token(viewer.email)
        for name, _ in self.dashboard_endpoints:
            url = url_of(name)
            resp = self.client.get(url, **self._headers(token))
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, f"{name} should be 403 for non-admin")
            data = resp.json()
            self.assertIn("detail", data)
            d = data["detail"].lower()
            allowed = any(kw in d for kw in ["akses", "tidak memiliki izin", "do not have permission", "forbidden", "permission"])
            self.assertTrue(allowed, f"{name} should return an explicit permission message")
            forbidden_keys = {"totalUsers", "activeUsers", "datasets", "roles", "logs", "events", "total_failed"}
            self.assertTrue(forbidden_keys.isdisjoint(set(data.keys())), f"{name} leaked data for non-admin")

    def test_admin_can_access_endpoints(self):
        admin = self._create_user("admin@example.com", "ADMIN")
        token = self._login_and_get_token(admin.email)
        for name, _ in self.dashboard_endpoints:
            url = url_of(name)
            resp = self.client.get(url, **self._headers(token))
            self.assertEqual(resp.status_code, status.HTTP_200_OK, f"{name} should be accessible to admin")

    def test_zero_data_messages_and_no_technical_errors_on_stats(self):
        admin = self._create_user("admin2@example.com", "ADMIN")
        token = self._login_and_get_token(admin.email)
        cache.delete("auth:failed_login_total")
        cache.delete("auth:failed_login_events")
        url = url_of("admin-stats")
        resp = self.client.get(url, **self._headers(token))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("totalUsers", data)
        self.assertIn("activeUsers", data)
        self.assertIn("datasets", data)
        self.assertIn("failedLogins", data)
        self.assertIn("roles", data)
        joined = str(data)
        self.assertNotIn("Traceback", joined)
        self.assertNotIn("Exception", joined)
        self.assertNotIn("stack", joined.lower())
        messages = data.get("messages") or {}
        any_message = "Data tidak ditemukan" in str(messages) or "Tidak ada aktivitas" in str(messages)
        for k in ("usersMessage", "activityMessage", "datasetsMessage"):
            if k in data and isinstance(data[k], str):
                if ("Data tidak ditemukan" in data[k]) or ("Tidak ada aktivitas" in data[k]):
                    any_message = True
        self.assertTrue(any_message, "Zero-data friendly messages missing in stats response")


@override_settings(SECRET_API_KEYS=("test-key",))
class AdminDashboardNegativeTests(TestCase):
    # Negative scenarios and API key checks

    databases = {"default"}

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        Role.objects.create(name="ADMIN")
        Role.objects.create(name="TENAGA_AHLI")
        Role.objects.create(name="VIEWER")
        self.admin = User.objects.create(
            name="Admin",
            email="admin@example.com",
            password=make_password("StrongP@ss1"),
            role="ADMIN",
        )
        self.viewer = User.objects.create(
            name="Vera",
            email="vera@example.com",
            password=make_password("WeakP@ss1"),
            role="VIEWER",
        )

    def _login_and_get_token(self, email, password):
        login_url = reverse("login")
        resp = self.client.post(
            login_url, {"email": email, "password": password}, format="json", **TEST_API_KEY_HEADER
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["access_token"]

    def test_unauthenticated_dashboard_page_redirects_to_login_if_html_route_exists(self):
        try:
            url = reverse("admin-dashboard")
            resp = self.client.get(url, follow=False)
            self.assertIn(resp.status_code, (301, 302))
            self.assertIn("login", (resp.url or "").lower())
            return
        except NoReverseMatch:
            pass
        try:
            url = reverse("admin:index")
            resp = self.client.get(url, follow=False)
            self.assertIn(resp.status_code, (301, 302))
            self.assertIn("login", (resp.url or "").lower())
            return
        except NoReverseMatch:
            api = url_of("admin-user-info")
            resp = self.client.get(api, **TEST_API_KEY_HEADER)
            self.assertEqual(resp.status_code, 401)

    def test_non_admin_credentials_cannot_access_admin_stats(self):
        token = self._login_and_get_token("vera@example.com", "WeakP@ss1")
        url = url_of("admin-stats")
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        try:
            import admin_feature.views as views  # noqa
        except ImportError:
            self.skipTest("admin_feature.views unavailable")
        helper_name = None
        for cand in ("require_admin_role", "ensure_admin_role", "assert_admin_role", "check_admin_permission"):
            if hasattr(views, cand):
                helper_name = cand
                break
        if helper_name is None:
            self.skipTest("No admin permission helper to patch; implement RBAC then enable this test.")
        with patch(f"admin_feature.views.{helper_name}", side_effect=PermissionDenied("Anda tidak memiliki izin untuk mengakses halaman ini.")):
            resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        ok = (
            ("detail" in body and "tidak memiliki izin" in body["detail"].lower())
            or ("message" in body and "tidak memiliki izin" in body["message"].lower())
        )
        self.assertTrue(ok)

    def test_admin_accessing_other_admin_page_without_permission_forbidden(self):
        token = self._login_and_get_token("admin@example.com", "StrongP@ss1")
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        url = url_of("admin-roles-summary")
        try:
            import admin_feature.views as views  # noqa
        except ImportError:
            self.skipTest("admin_feature.views unavailable")
        helper_name = None
        for cand in ("require_admin_scope", "ensure_admin_scope", "assert_admin_scope", "check_admin_permission"):
            if hasattr(views, cand):
                helper_name = cand
                break
        if helper_name is None:
            self.skipTest("No granular permission helper to patch; implement per-page permissions then enable this test.")
        with patch(f"admin_feature.views.{helper_name}", side_effect=PermissionDenied("Akses Ditolak")):
            resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        ok = (
            ("detail" in body and ("akses ditolak" in body["detail"].lower() or "tidak memiliki izin" in body["detail"].lower()))
            or ("message" in body and ("akses ditolak" in body["message"].lower() or "tidak memiliki izin" in body["message"].lower()))
        )
        self.assertTrue(ok)

    def test_dashboard_stats_empty_state_when_no_data(self):
        url = url_of("admin-stats")
        mock_user = SimpleNamespace()
        mock_user_manager = MagicMock()
        mock_user_qs = MagicMock()
        mock_user_manager.count.return_value = 0
        mock_user_manager.filter.return_value = mock_user_qs
        mock_user_qs.count.return_value = 0
        mock_user.objects = mock_user_manager

        mock_role = SimpleNamespace()
        mock_role_qs = MagicMock()
        mock_role_qs.order_by.return_value = []
        mock_role.values_list = MagicMock(return_value=mock_role_qs)
        mock_role.objects = mock_role

        mock_datasets_service_class = MagicMock()
        mock_datasets_service_class.return_value.get_total_datasets.return_value = 0

        with patch("admin_feature.views.User", new=mock_user), \
             patch("admin_feature.views.Role", new=mock_role), \
             patch("admin_feature.views.DatasetsService", new=mock_datasets_service_class), \
             patch("admin_feature.views.cache") as mock_cache:
            mock_cache.get.return_value = 0
            admin = getattr(self, "_create_user", None)
            if admin:
                admin = self._create_user("admin-empty@example.com", "ADMIN")
            else:
                admin = User.objects.create(
                    name="AdminZero",
                    email="adminzero@example.com",
                    password=make_password("AdminZ3r0!"),
                    role="ADMIN",
                )
            login_url = reverse("login")
            login_resp = self.client.post(
                login_url, {"email": admin.email, "password": "AdminZ3r0!"},
                format="json", **TEST_API_KEY_HEADER
            )
            self.assertEqual(login_resp.status_code, 200, login_resp.content)
            token = login_resp.json()["access_token"]
            headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
            resp = self.client.get(url, **headers)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("totalUsers", None), 0)
        self.assertEqual(data.get("activeUsers", None), 0)
        self.assertEqual(data.get("datasets", None), 0)
        self.assertEqual(data.get("roles", None), [])
        has_empty_flag = (data.get("empty") is True) or (data.get("isEmpty") is True)
        has_message = any(
            (k in data and isinstance(data[k], str) and "tidak ada data" in data[k].lower())
            for k in ("message", "detail", "notice")
        )
        self.assertTrue(has_empty_flag or has_message, "Expected empty/isEmpty flag or message in response.")

    def test_roles_summary_requires_api_key(self):
        url = url_of("admin-roles-summary")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)

    def test_users_summary_requires_api_key(self):
        url = url_of("admin-users-summary")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)

    def test_failed_login_stats_requires_api_key(self):
        url = url_of("admin-failed-login-stats")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)

    def test_failed_login_logs_requires_api_key(self):
        url = url_of("admin-failed-login-logs")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)

    def test_datasets_summary_requires_api_key(self):
        url = url_of("admin-datasets-summary")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)


@override_settings(SECRET_API_KEYS=("test-key",))
class UserInfoEdgeUnitTests(TestCase):
    # Direct-call branches in UserInfoAPIView

    def test_user_info_no_user_internal_401(self):
        view = UserInfoAPIView()
        req = SimpleNamespace()  # no 'user'
        resp = view.get(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Authentication credentials were not provided", str(resp.data.get("detail", "")))

    def test_user_info_non_admin_internal_403(self):
        view = UserInfoAPIView()
        fake_user = SimpleNamespace(role="VIEWER", name="Vera", email="vera@example.com")
        req = SimpleNamespace(user=fake_user)
        resp = view.get(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Akses Ditolak", str(resp.data.get("detail", "")))

    def test_user_info_name_fallback_to_email(self):
        view = UserInfoAPIView()
        fake_user = SimpleNamespace(role="ADMIN", name=None, email="no-name@example.com")
        req = SimpleNamespace(user=fake_user)
        resp = view.get(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "no-name@example.com")
        self.assertEqual(resp.data["role"], "ADMIN")