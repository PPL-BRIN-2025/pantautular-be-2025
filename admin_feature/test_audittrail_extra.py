import os
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pantau_tular.test_settings")
django.setup()

from django.test import TestCase
from django.utils import timezone as django_timezone
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory, force_authenticate

from admin_feature import audittrail, audittrail1, signals
from admin_feature.models import AdminUserLog
from admin_feature.views import (
    AdminUserLogsAPIView,
    AdminUserLogsAllAPIView,
    AdminUserLogDetailAPIView,
    AdminUserLogUpdateAPIView,
)


class AuditTrailModuleTests(TestCase):
    def test_write_log_uses_explicit_user(self):
        user = SimpleNamespace(name="Admin Tester", email="admin@example.com")
        audittrail.write_log(user=user, action="VIEW", detail="Checked dashboard")

        entry = AdminUserLog.objects.latest("id")
        self.assertEqual(entry.username, "Admin Tester")
        self.assertEqual(entry.email, "admin@example.com")
        self.assertEqual(entry.action, "VIEW")
        self.assertEqual(entry.detail, "Checked dashboard")

    def test_write_log_falls_back_to_request_user(self):
        request = SimpleNamespace(user=SimpleNamespace(username="req-user", email="req@example.com"))
        audittrail.write_log(request=request, action="LOGIN")

        entry = AdminUserLog.objects.latest("id")
        self.assertEqual(entry.username, "req-user")
        self.assertEqual(entry.email, "req@example.com")
        self.assertEqual(entry.action, "LOGIN")

    def test_write_log_defaults_to_anonymous(self):
        audittrail.write_log(user=None, action="NONE", detail="no user")

        entry = AdminUserLog.objects.latest("id")
        self.assertEqual(entry.username, "anonymous")
        self.assertEqual(entry.action, "NONE")

        # request without user should keep anonymous
        audittrail.write_log(request=SimpleNamespace(user=None), user=None, action="REQNONE")
        entry = AdminUserLog.objects.latest("id")
        self.assertEqual(entry.username, "anonymous")


class AuditTrail1HelperTests(TestCase):
    def test_helper_functions_and_logging(self):
        # _shorten / _ensure_text / _safe_email
        self.assertEqual(audittrail1._shorten(None), "")
        self.assertEqual(audittrail1._shorten("abc", 10), "abc")
        self.assertEqual(audittrail1._shorten("x" * 40, 10), ("x" * 10) + "...")
        self.assertEqual(audittrail1._ensure_text(None), "")
        self.assertEqual(audittrail1._ensure_text(5), "5")
        self.assertEqual(audittrail1._safe_email("test@example.com"), "test@example.com")

        # write_log should call AdminUserLog.objects.create and _debug_trace
        with patch.object(audittrail1, "AdminUserLog") as mock_model, patch.object(audittrail1, "print") as mock_print:
            mock_model.objects.create.return_value = SimpleNamespace()
            audittrail1.write_log(
                user=SimpleNamespace(name="Helper User", email="help@example.com"),
                action="HELP",
                detail="detail" * 20,
                note="note" * 20,
            )
            mock_model.objects.create.assert_called_once()
            self.assertTrue(mock_print.called)

        with patch.object(audittrail1, "AUDIT_DEBUG_DEFAULT", False):
            audittrail1._debug_trace("user", "ACT", "detail", "note")

    def test_write_log_returns_metadata(self):
        with patch.object(audittrail1, "AdminUserLog") as mock_model:
            mock_model.objects.create.return_value = SimpleNamespace()
            result = audittrail1.write_log(user=None, action=None, detail="", note="notes")
            self.assertTrue(result["ok"])
            self.assertEqual(result["user"], "anonymous")
            self.assertIn("timestamp", result)

            request = SimpleNamespace(user=SimpleNamespace(username="from-request", email="req@example.com"))
            audittrail1.write_log(request=request, action="REQ", detail="detail", note="note")
            request_empty = SimpleNamespace(user=None)
            audittrail1.write_log(request=request_empty, user=None, action="REQNONE", detail="", note="")


class AdminFeatureSignalsTests(TestCase):
    def setUp(self):
        self.user = SimpleNamespace(name="Signal User", email="signal@example.com")

    def test_login_signal_calls_audit(self):
        with patch("admin_feature.signals.write_log") as mock_write:
            request = SimpleNamespace(user=self.user)
            signals._on_login(sender=None, request=request, user=self.user)
            mock_write.assert_called_once()

    def test_logout_signal_calls_audit(self):
        with patch("admin_feature.signals.write_log") as mock_write:
            request = SimpleNamespace(user=self.user)
            signals._on_logout(sender=None, request=request, user=self.user)
            mock_write.assert_called_once()

    def test_login_failed_signal_uses_credentials(self):
        with patch("admin_feature.signals.write_log") as mock_write:
            signals._on_login_failed(
                sender=None,
                credentials={"username": "bad-user"},
                request=None,
            )
            detail = mock_write.call_args.kwargs["detail"]
            self.assertIn("bad-user", detail)


class AdminUserLogsAPIViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = SimpleNamespace(role="ADMIN", is_authenticated=True, name="Admin")
        self._orig_auth = AdminUserLogsAPIView.authentication_classes
        self._orig_perm = AdminUserLogsAPIView.permission_classes
        self._orig_all_auth = AdminUserLogsAllAPIView.authentication_classes
        self._orig_all_perm = AdminUserLogsAllAPIView.permission_classes
        AdminUserLogsAPIView.authentication_classes = []
        AdminUserLogsAPIView.permission_classes = []
        AdminUserLogsAllAPIView.authentication_classes = []
        AdminUserLogsAllAPIView.permission_classes = []
        self.log1 = AdminUserLog.objects.create(
            username="Alpha",
            email="alpha@example.com",
            action="VIEW",
            detail="First",
            note="",
            timestamp=django_timezone.now() - timedelta(days=1),
        )
        self.log2 = AdminUserLog.objects.create(
            username="Bravo",
            email="bravo@example.com",
            action="UPDATE",
            detail="Second entry detail",
            note="extra",
            timestamp=django_timezone.now(),
        )

    def _get_view(self, query=None):
        request = self.factory.get(
            "/admin-feature/logs",
            query or {"search": "Bravo", "sort": "timestamp:asc", "start": "invalid-date"},
        )
        force_authenticate(request, user=self.admin)
        return AdminUserLogsAPIView.as_view()(request)

    def test_get_includes_filters_and_handles_invalid_dates(self):
        response = self._get_view()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["data"][0]["username"], "Bravo")

        response = self._get_view({"search": "", "sort": "timestamp:desc", "end": "invalid"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 2)

    def test_post_creates_and_handles_invalid_payload(self):
        payload = {
            "username": "Charlie",
            "email": "charlie@example.com",
            "action": "CREATE",
            "detail": "created log",
            "note": "",
        }
        request = self.factory.post("/admin-feature/logs", payload, format="json")
        force_authenticate(request, user=self.admin)
        response = AdminUserLogsAPIView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(AdminUserLog.objects.filter(username="Charlie").count(), 1)

        payload_with_timestamp = {
            "username": "Delta",
            "email": "delta@example.com",
            "action": "VIEW",
            "detail": "explicit timestamp",
            "note": "",
            "timestamp": django_timezone.now().isoformat(),
        }
        request2 = self.factory.post("/admin-feature/logs", payload_with_timestamp, format="json")
        force_authenticate(request2, user=self.admin)
        response2 = AdminUserLogsAPIView.as_view()(request2)
        self.assertEqual(response2.status_code, 201)

        bad_request = self.factory.post("/admin-feature/logs", {"username": ""}, format="json")
        force_authenticate(bad_request, user=self.admin)
        response = AdminUserLogsAPIView.as_view()(bad_request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.data)

    def test_audit_log_mixin_swallows_errors(self):
        with patch("admin_feature.views.write_log", side_effect=RuntimeError("boom")):
            request = self.factory.get("/admin-feature/logs/all")
            force_authenticate(request, user=self.admin)
            response = AdminUserLogsAllAPIView.as_view()(request)
            self.assertEqual(response.status_code, 200)

    def tearDown(self):
        AdminUserLogsAPIView.authentication_classes = self._orig_auth
        AdminUserLogsAPIView.permission_classes = self._orig_perm
        AdminUserLogsAllAPIView.authentication_classes = self._orig_all_auth
        AdminUserLogsAllAPIView.permission_classes = self._orig_all_perm


class AdminFeatureModelTests(TestCase):
    def test_admin_user_log_str(self):
        log = AdminUserLog.objects.create(
            username="Demo",
            email="demo@example.com",
            action="UPDATE",
            detail="Changed role",
            note="",
        )
        self.assertIn("Demo", str(log))
        self.assertIn("UPDATE", str(log))

    def test_pt_backend_user_str(self):
        from admin_feature.models import PtBackendUser

        user = PtBackendUser(name="PT User", email="pt@example.com")
        self.assertEqual(str(user), "PT User (pt@example.com)")


class AdminUserLogDetailViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = SimpleNamespace(role="ADMIN", is_authenticated=True)
        self.log = AdminUserLog.objects.create(
            username="Detail",
            email="detail@example.com",
            action="VIEW",
            detail="Some detail",
            note="",
        )
        self._orig_detail_auth = AdminUserLogDetailAPIView.authentication_classes
        self._orig_detail_perm = AdminUserLogDetailAPIView.permission_classes
        self._orig_update_auth = AdminUserLogUpdateAPIView.authentication_classes
        self._orig_update_perm = AdminUserLogUpdateAPIView.permission_classes
        AdminUserLogDetailAPIView.authentication_classes = []
        AdminUserLogDetailAPIView.permission_classes = []
        AdminUserLogUpdateAPIView.authentication_classes = []
        AdminUserLogUpdateAPIView.permission_classes = []

    def tearDown(self):
        AdminUserLogDetailAPIView.authentication_classes = self._orig_detail_auth
        AdminUserLogDetailAPIView.permission_classes = self._orig_detail_perm
        AdminUserLogUpdateAPIView.authentication_classes = self._orig_update_auth
        AdminUserLogUpdateAPIView.permission_classes = self._orig_update_perm

    def test_retrieve_logs(self):
        request = self.factory.get(f"/admin-feature/logs/{self.log.id}/")
        force_authenticate(request, user=self.admin)
        response = AdminUserLogDetailAPIView.as_view()(request, id=self.log.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.log.id)

        request_update = self.factory.get(f"/admin-feature/logs/{self.log.id}/")
        force_authenticate(request_update, user=self.admin)
        response_update = AdminUserLogUpdateAPIView.as_view()(request_update, id=self.log.id)
        self.assertEqual(response_update.status_code, 200)

    def test_partial_update_logs(self):
        request = self.factory.patch(
            f"/admin-feature/logs/{self.log.id}/",
            {"detail": "Updated detail"},
            format="json",
        )
        force_authenticate(request, user=self.admin)
        response = AdminUserLogUpdateAPIView.as_view()(request, id=self.log.id)
        self.assertEqual(response.status_code, 200)
        self.log.refresh_from_db()
        self.assertEqual(self.log.detail, "Updated detail")
