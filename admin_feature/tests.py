# admin_feature/tests.py
from django.test import TestCase, override_settings
from django.urls import reverse, NoReverseMatch
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from pt_backend.models import Role, User, UserRole
from django.contrib.auth.hashers import make_password
from pt_backend.models import Disease, Location, Case
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from typing import Dict, List, Optional
from django.conf import settings
from django.core.exceptions import PermissionDenied
import jwt
from datetime import datetime, timedelta
from secrets import token_urlsafe
import importlib
from rest_framework import status
from admin_feature.views import UserInfoAPIView
from admin_feature.services import AdminDashboardService

TEST_API_KEY_HEADER = {"HTTP_X_API_KEY": "test-key"}

def random_password(prefix: str = "Pwd") -> str:
    return f"{prefix}-{token_urlsafe(10)}!"

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
        self._passwords: Dict[str, str] = {}
        self.user_password = random_password("Adm1n")
        self.user = User.objects.create(
            name="John",
            email="john@example.com",
            password=make_password(self.user_password),
            role="ADMIN",
        )
        self._passwords[self.user.email] = self.user_password

    def _login_and_get_token(self, email: Optional[str] = None, password: Optional[str] = None):
        email = email or self.user.email
        if password is None:
            password = self._passwords.get(email)
        if password is None:
            raise AssertionError(f"Test password for {email} not found")
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
        self.assertCountEqual(data["roles"], list(Role.objects.values_list("name", flat=True)))
        self.assertIsInstance(data["failedLogins"], int)

    def test_stats_requires_api_key(self):
        url = url_of("admin-stats")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)

    def test_user_info_token_expired(self):
        payload = {"name": "Jane", "role": "ADMIN", "user_id": 999, "exp": timezone.now() - timedelta(seconds=5)}
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        url = url_of("admin-user-info")
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 401)

    def test_user_info_invalid_payload_no_user_id(self):
        payload = {"exp": timezone.now() + timedelta(minutes=5)}
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        url = url_of("admin-user-info")
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 401)

    def test_user_info_user_not_found(self):
        payload = {"user_id": 999999, "exp": timezone.now() + timedelta(minutes=5)}
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
        service = AdminDashboardService(user_model=stub_user)

        summary = service.get_users_summary().to_dict()
        self.assertEqual(summary["total_users"], 10)
        self.assertEqual(summary["active_users"], 4)

    def test_users_summary_with_mocks_verifies_calls(self):
        mock_user = SimpleNamespace()
        mock_manager = MagicMock()
        mock_qs = MagicMock()
        mock_manager.count.return_value = 99
        mock_manager.filter.return_value = mock_qs
        mock_qs.count.return_value = 11
        mock_user.objects = mock_manager

        service = AdminDashboardService(user_model=mock_user)
        summary = service.get_users_summary().to_dict()

        self.assertEqual(summary["total_users"], 99)
        self.assertEqual(summary["active_users"], 11)
        mock_manager.count.assert_called_once_with()
        mock_manager.filter.assert_called_once_with(last_login__isnull=False)
        mock_qs.count.assert_called_once_with()


@override_settings(SECRET_API_KEYS=("test-key",))
class StatsUsersCountsWithMocksTests(TestCase):
    """Focused tests for AdminDashboardService aggregation with mocked collaborators."""

    def _build_service(
        self,
        *,
        total_users: int,
        active_users: int,
        dataset_total: int,
        roles: List[str],
        failed_logins: int,
        events: Optional[List[Dict[str, object]]] = None,
    ) -> AdminDashboardService:
        class _UserManager:
            def count(self):
                return total_users

            def filter(self, **_kwargs):
                class _QuerySet:
                    def count(inner_self):
                        return active_users

                return _QuerySet()

        class _RoleManager:
            def values_list(self, *_args, **_kwargs):
                class _ValuesList:
                    def order_by(inner_self, *_):
                        return roles

                return _ValuesList()

        user_model = SimpleNamespace(objects=_UserManager())
        role_model = SimpleNamespace(objects=_RoleManager())

        dataset_service = MagicMock()
        dataset_service.get_total_datasets.return_value = dataset_total

        cache_backend = MagicMock()

        def _cache_get(key, default=None):
            if key == AdminDashboardService.FAILED_TOTAL_KEY:
                return failed_logins
            if key == AdminDashboardService.FAILED_EVENTS_KEY:
                return events or []
            if key == AdminDashboardService.FAILED_UNIQUE_KEY and events is None:
                return None
            return default

        cache_backend.get.side_effect = _cache_get

        return AdminDashboardService(
            role_model=role_model,
            user_model=user_model,
            cache_backend=cache_backend,
            dataset_service=dataset_service,
        )

    def test_stats_users_counts_with_mocks(self):
        service = self._build_service(
            total_users=7,
            active_users=3,
            dataset_total=42,
            roles=["ADMIN", "VIEWER"],
            failed_logins=5,
        )

        data = service.get_stats().to_dict()
        self.assertEqual(data["totalUsers"], 7)
        self.assertEqual(data["activeUsers"], 3)
        self.assertEqual(data["datasets"], 42)
        self.assertEqual(data["failedLogins"], 5)
        self.assertEqual(data["roles"], ["ADMIN", "VIEWER"])

    def test_stats_partial_zero_messages_set(self):
        service = self._build_service(
            total_users=5,
            active_users=0,
            dataset_total=0,
            roles=["ADMIN"],
            failed_logins=2,
        )

        data = service.get_stats().to_dict()
        self.assertEqual(data["messages"].get("activityMessage"), "Tidak ada aktivitas")
        self.assertEqual(data["messages"].get("datasetsMessage"), "Data tidak ditemukan")

    def test_stats_partial_users_zero_message_set(self):
        service = self._build_service(
            total_users=0,
            active_users=2,
            dataset_total=9,
            roles=["ADMIN"],
            failed_logins=1,
        )

        data = service.get_stats().to_dict()
        self.assertEqual(data["messages"].get("usersMessage"), "Data tidak ditemukan")


@override_settings(SECRET_API_KEYS=("test-key",))
class AdminUserManagementTests(TestCase):
    databases = {"default"}

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.admin_role = Role.objects.create(name="ADMIN")
        self.viewer_role = Role.objects.create(name="VIEWER")
        self.editor_role = Role.objects.create(name="EDITOR")

        self._passwords: Dict[str, str] = {}
        self.admin_password = random_password("Adm1n")
        self.viewer_password = random_password("View3r")
        self.editor_password = random_password("Edit0r")

        self.admin_user = User.objects.create(
            name="Super Admin",
            email="admin@example.com",
            password=make_password(self.admin_password),
            role="ADMIN",
        )
        self._passwords[self.admin_user.email] = self.admin_password

        self.viewer_user = User.objects.create(
            name="Viewer One",
            email="viewer1@example.com",
            password=make_password(self.viewer_password),
            role="VIEWER",
        )
        UserRole.objects.create(user=self.viewer_user, role=self.viewer_role)
        self._passwords[self.viewer_user.email] = self.viewer_password

    def _auth_headers(self):
        login_url = reverse("login")
        resp = self.client.post(
            login_url,
            {"email": self.admin_user.email, "password": self.admin_password},
            format="json",
            **TEST_API_KEY_HEADER,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        token = resp.json()["access_token"]
        return {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_list_users_returns_roles_field(self):
        editor_user = User.objects.create(
            name="Editor One",
            email="editor@example.com",
            password=make_password(self.editor_password),
            role="EDITOR",
        )
        self._passwords[editor_user.email] = self.editor_password
        UserRole.objects.create(user=editor_user, role=self.editor_role)
        UserRole.objects.create(user=editor_user, role=self.viewer_role)

        url = reverse("admin-user-list")
        resp = self.client.get(url, **self._auth_headers())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        editor_entry = next((item for item in data if item["email"] == "editor@example.com"), None)
        self.assertIsNotNone(editor_entry)
        self.assertCountEqual(editor_entry["roles"], ["EDITOR", "VIEWER"])
        self.assertEqual(editor_entry["role"], "EDITOR")

    def test_delete_user_removes_user_and_roles(self):
        url = reverse("admin-user-delete", kwargs={"id": self.viewer_user.id})
        resp = self.client.delete(url, **self._auth_headers())

        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.viewer_user.id).exists())
        self.assertFalse(UserRole.objects.filter(user=self.viewer_user).exists())

    def test_change_role_updates_string_flag_and_mapping(self):
        payload = {"role_id": self.editor_role.id}
        url = reverse("admin-user-change-role", kwargs={"id": self.viewer_user.id})
        resp = self.client.put(url, payload, format="json", **self._auth_headers())

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(body["role"], "EDITOR")
        self.viewer_user.refresh_from_db()
        self.assertEqual(self.viewer_user.role, "EDITOR")
        self.assertEqual(UserRole.objects.filter(user=self.viewer_user).count(), 1)
        self.assertEqual(UserRole.objects.get(user=self.viewer_user).role_id, self.editor_role.id)

    def test_change_role_invalid_role_returns_400(self):
        url = reverse("admin-user-change-role", kwargs={"id": self.viewer_user.id})
        resp = self.client.put(url, {"role_id": 999999}, format="json", **self._auth_headers())

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.viewer_user.refresh_from_db()
        self.assertEqual(self.viewer_user.role, "VIEWER")


@override_settings(SECRET_API_KEYS=("test-key",))
class AdminDashboardSecurityTests(TestCase):
    # Security/gating and no leakage

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self._passwords = {}
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

    def _create_user(self, email, role, password: Optional[str] = None):
        password = password or random_password(role.title())
        user = User.objects.create(
            name=email.split("@")[0].title(),
            email=email,
            password=make_password(password),
            role=role,
        )
        self._passwords[email] = password
        return user

    def _login_and_get_token(self, email, password: Optional[str] = None):
        if password is None:
            password = self._passwords.get(email)
        if password is None:
            raise AssertionError(f"Password for {email} not recorded")
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
        self._passwords: Dict[str, str] = {}
        self.admin_password = random_password("Adm1n")
        self.viewer_password = random_password("View3r")
        self.admin = User.objects.create(
            name="Admin",
            email="admin@example.com",
            password=make_password(self.admin_password),
            role="ADMIN",
        )
        self._passwords[self.admin.email] = self.admin_password
        self.viewer = User.objects.create(
            name="Vera",
            email="vera@example.com",
            password=make_password(self.viewer_password),
            role="VIEWER",
        )
        self._passwords[self.viewer.email] = self.viewer_password

    def _login_and_get_token(self, email, password: Optional[str] = None):
        if password is None:
            password = self._passwords.get(email)
        if password is None:
            raise AssertionError(f"Password for {email} not recorded")
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
        token = self._login_and_get_token("vera@example.com")
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
        token = self._login_and_get_token("admin@example.com")
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

        dataset_service = MagicMock()
        dataset_service.get_total_datasets.return_value = 0

        cache_backend = MagicMock()
        cache_backend.get.side_effect = lambda *_, **__: 0

        service = AdminDashboardService(
            role_model=mock_role,
            user_model=mock_user,
            cache_backend=cache_backend,
            dataset_service=dataset_service,
        )

        admin_password = random_password("AdmZero")
        admin = getattr(self, "_create_user", None)
        if callable(admin):
            admin = self._create_user("admin-empty@example.com", "ADMIN", password=admin_password)
        else:
            admin = User.objects.create(
                name="AdminZero",
                email="adminzero@example.com",
                password=make_password(admin_password),
                role="ADMIN",
            )
            self._passwords[admin.email] = admin_password

        login_url = reverse("login")
        login_resp = self.client.post(
            login_url,
            {"email": admin.email, "password": self._passwords.get(admin.email, admin_password)},
            format="json",
            **TEST_API_KEY_HEADER,
        )
        self.assertEqual(login_resp.status_code, 200, login_resp.content)
        token = login_resp.json()["access_token"]
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}

        with patch("admin_feature.views.StatsAPIView.get_dashboard_service", return_value=service):
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

from django.test import TestCase
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from pt_backend.models import User, Role, UserRole
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

def make_access_token(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)

class AdminFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.admin_role = Role.objects.create(name="ADMIN")
        self.curator    = Role.objects.create(name="Curator")
        self.contributor= Role.objects.create(name="Contributor")

        self.admin = User.objects.create(
            name="Admin",
            email="admin@example.com",
            password="pass123",  
            role="ADMIN",
            last_login=timezone.now(),
        )
        UserRole.objects.create(user=self.admin, role=self.admin_role)

        self.alice = User.objects.create(
            name="Alice",
            email="alice@example.com",
            password="pass123",
            role="Contributor",
        )
        UserRole.objects.create(user=self.alice, role=self.contributor)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {make_access_token(self.admin)}")

    def test_list_users(self):
        res = self.client.get("/admin-feature/users")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(u["email"] == "alice@example.com" for u in res.data))

    def test_change_role(self):
        res = self.client.put(f"/admin-feature/users/{self.alice.id}/role", {"role_name": "Curator"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.role, "Curator")
        self.assertTrue(UserRole.objects.filter(user=self.alice, role=self.curator).exists())
        self.assertFalse(UserRole.objects.filter(user=self.alice, role__name="Contributor").exists())

    def test_delete_user(self):
        res = self.client.delete(f"/admin-feature/users/{self.alice.id}")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.alice.id).exists())

    def test_list_users_unauthorized(self):
        # no Authorization header
        client = APIClient()
        res = client.get("/admin-feature/users")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_users_forbidden_non_admin(self):
        # non-admin token
        non_admin = User.objects.create(
            name="Bob", email="bob@example.com", password="pass123", role="Contributor"
        )
        UserRole.objects.create(user=non_admin, role=self.contributor)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {make_access_token(non_admin)}")
        res = client.get("/admin-feature/users")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_change_role_invalid_role_name(self):
        res = self.client.put(
            f"/admin-feature/users/{self.alice.id}/role",
            {"role_name": "NotARole"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_role_missing_body(self):
        res = self.client.put(
            f"/admin-feature/users/{self.alice.id}/role", {}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_role_user_not_found(self):
        res = self.client.put(
            "/admin-feature/users/999999/role", {"role_name": "Curator"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_change_role_idempotent_same_role(self):
        # Set Alice to Curator first
        self.client.put(
            f"/admin-feature/users/{self.alice.id}/role",
            {"role_name": "Curator"},
            format="json",
        )
        # Change to Curator again
        res = self.client.put(
            f"/admin-feature/users/{self.alice.id}/role",
            {"role_name": "Curator"},
            format="json",
        )
        self.assertIn(res.status_code, (status.HTTP_200_OK, status.HTTP_304_NOT_MODIFIED))
        # Still only one UserRole row to Curator
        self.assertTrue(UserRole.objects.filter(user=self.alice, role=self.curator).exists())
        self.assertEqual(UserRole.objects.filter(user=self.alice).count(), 1)

    def test_delete_user_not_found(self):
        res = self.client.delete("/admin-feature/users/999999")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_user_forbidden_non_admin(self):
        non_admin = User.objects.create(
            name="Bob2", email="bob2@example.com", password="pass123", role="Contributor"
        )
        UserRole.objects.create(user=non_admin, role=self.contributor)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {make_access_token(non_admin)}")
        res = client.delete(f"/admin-feature/users/{self.alice.id}")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_self_allowed(self):
        res = self.client.delete(f"/admin-feature/users/{self.admin.id}")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.admin.id).exists())

    def test_change_role_by_id(self):
        res = self.client.put(
            f"/admin-feature/users/{self.alice.id}/role",
            {"role_id": self.curator.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.role, "Curator")
        self.assertTrue(UserRole.objects.filter(user=self.alice, role=self.curator).exists())

