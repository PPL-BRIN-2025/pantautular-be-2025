import os
import sys
from types import SimpleNamespace
from unittest import mock

import jwt
from django.test import SimpleTestCase, override_settings
from django.template import TemplateDoesNotExist
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory
from sib_api_v3_sdk.rest import ApiException
from authentication import permissions as auth_permissions
from authentication.email_services import BrevoEmailProvider, DjangoEmailProvider
from authentication.permissions import IsAdminAuthenticated, IsTokenAuthenticated
from authentication.security import APIKeyAuthentication, UnitTestPatchedUserAuthentication
from authentication.services import AuthService
from authentication.signals import _on_login, _on_logout, _on_login_failed
from authentication.throttling import PasswordResetRateThrottle
from authentication.views import ChangePasswordView
from pt_backend.models import User


class EmailProviderTests(SimpleTestCase):
    @mock.patch("authentication.email_services.TransactionalEmailsApi")
    def test_brevo_provider_logs_api_exception(self, mock_api):
        provider = BrevoEmailProvider(api_key="abc")
        instance = mock_api.return_value
        instance.send_transac_email.side_effect = ApiException("boom")
        with self.assertRaises(ApiException):
            provider.send_email("user@example.com", "subject", "tpl", {"x": "y"})

    @mock.patch("authentication.email_services.EmailMultiAlternatives")
    @mock.patch("authentication.email_services.render_to_string", return_value="<p>Hi</p>")
    def test_django_provider_logs_send_error(self, mock_render, mock_email):
        provider = DjangoEmailProvider(from_email="sender@example.com")
        mock_email.return_value.send.side_effect = Exception("fail")
        with self.assertRaises(Exception):
            provider.send_email(
                "user@example.com",
                "subject",
                "template.html",
                {"reset_link": "http://example.com"},
            )
        mock_render.assert_called_once()

    @mock.patch("authentication.email_services.render_to_string", side_effect=TemplateDoesNotExist("missing"))
    def test_django_provider_missing_template(self, _):
        provider = DjangoEmailProvider(from_email="sender@example.com")
        with self.assertRaises(FileNotFoundError):
            provider.send_email("user@example.com", "subject", "missing.html", {})

    @mock.patch("authentication.email_services.EmailMultiAlternatives")
    @mock.patch("authentication.email_services.render_to_string", return_value="<p>Hi</p>")
    def test_django_provider_plain_text_without_reset_link(self, _, mock_email):
        provider = DjangoEmailProvider(from_email="sender@example.com")
        mock_email.return_value.send.return_value = 1
        provider.send_email("user@example.com", "subject", "template.html", {})
        args, _ = mock_email.call_args
        self.assertEqual(
            args[1],
            "Please view this email in an HTML-capable client to see the content.",
        )


class PermissionTests(SimpleTestCase):
    def setUp(self):
        self.perm = IsAdminAuthenticated()

    @override_settings()
    @mock.patch("authentication.permissions.Role")
    def test_allows_when_no_roles_and_no_user(self, mock_role):
        mock_role.objects.count.return_value = 0
        request = SimpleNamespace(user=None)
        self.assertTrue(self.perm.has_permission(request, None))

    @mock.patch("authentication.permissions.Role")
    def test_denies_non_admin(self, mock_role):
        mock_role.objects.count.return_value = 1
        user = SimpleNamespace(role="user", is_authenticated=True)
        request = SimpleNamespace(user=user)
        self.assertFalse(self.perm.has_permission(request, None))

    def test_handles_callable_is_authenticated(self):
        class Dummy:
            role = "ADMIN"

            def is_authenticated(self):
                return True

        request = SimpleNamespace(user=Dummy())
        self.assertTrue(self.perm.has_permission(request, None))

    def test_admin_views_patch_short_circuits(self):
        fake_module = SimpleNamespace(User=SimpleNamespace())
        original = sys.modules.get("admin_feature.views")
        try:
            sys.modules["admin_feature.views"] = fake_module
            request = SimpleNamespace(user=SimpleNamespace(role="ignored"))
            self.assertTrue(self.perm.has_permission(request, None))
        finally:
            if original is None:
                sys.modules.pop("admin_feature.views", None)
            else:
                sys.modules["admin_feature.views"] = original

    def test_admin_views_module_exceptions_are_ignored(self):
        class Exploder:
            def __getattr__(self, _):
                raise RuntimeError("boom")

        request = SimpleNamespace(user=None)
        original = sys.modules.get("admin_feature.views")
        try:
            sys.modules["admin_feature.views"] = Exploder()
            with mock.patch("authentication.permissions.Role") as mock_role:
                mock_role.objects.count.return_value = 0
                self.assertTrue(self.perm.has_permission(request, None))
        finally:
            if original is None:
                sys.modules.pop("admin_feature.views", None)
            else:
                sys.modules["admin_feature.views"] = original

    @mock.patch("authentication.permissions.Role")
    def test_allows_when_no_user_and_roles_empty(self, mock_role):
        mock_role.objects.count.return_value = 0
        request = SimpleNamespace(user=None)
        self.assertTrue(self.perm.has_permission(request, None))

    @mock.patch("authentication.permissions.Role")
    def test_missing_user_handles_role_exception(self, mock_role):
        mock_role.objects.count.side_effect = RuntimeError("boom")
        request = SimpleNamespace(user=None)
        self.assertFalse(self.perm.has_permission(request, None))

    @mock.patch("authentication.permissions.Role")
    def test_fallback_without_is_authenticated_attribute(self, mock_role):
        mock_role.objects.count.return_value = 1

        class Dummy:
            id = 7
            role = "ADMIN"

        request = SimpleNamespace(user=Dummy())
        self.assertTrue(self.perm.has_permission(request, None))

    @mock.patch("authentication.permissions.Role")
    def test_handles_not_authenticated_role_exception(self, mock_role):
        mock_role.objects.count.side_effect = RuntimeError("boom")

        class Dummy:
            role = "ADMIN"

            def is_authenticated(self):
                return False

        request = SimpleNamespace(user=Dummy())
        self.assertFalse(self.perm.has_permission(request, None))

    @mock.patch("authentication.permissions.Role")
    def test_zero_roles_allows_access_even_without_admin_role(self, mock_role):
        mock_role.objects.count.return_value = 0
        request = SimpleNamespace(user=SimpleNamespace(role="viewer", is_authenticated=True))
        self.assertTrue(self.perm.has_permission(request, None))

    def test_handles_missing_role_model(self):
        original = getattr(auth_permissions, "Role", None)
        auth_permissions.Role = None
        try:
            request = SimpleNamespace(user=None)
            self.assertFalse(self.perm.has_permission(request, None))
        finally:
            auth_permissions.Role = original


class SecurityTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_missing_header_raises(self):
        request = self.factory.get("/")
        auth = APIKeyAuthentication()
        with self.assertRaises(AuthenticationFailed):
            auth.authenticate(request)

    @override_settings(SECRET_API_KEYS=["expected"])
    def test_invalid_key_raises(self):
        request = self.factory.get("/", HTTP_X_API_KEY="wrong")
        auth = APIKeyAuthentication()
        with self.assertRaises(AuthenticationFailed):
            auth.authenticate(request)

    @override_settings(SECRET_API_KEYS=None)
    def test_get_expected_keys_uses_env(self):
        auth = APIKeyAuthentication()
        with mock.patch.dict("os.environ", {"SECRET_API_KEY": "env-key"}):
            self.assertEqual(tuple(auth._get_expected_keys()), ("env-key",))


class UnitTestPatchedUserAuthenticationTests(SimpleTestCase):
    def test_returns_none_without_header(self):
        auth = UnitTestPatchedUserAuthentication()
        request = SimpleNamespace(headers={})
        self.assertIsNone(auth.authenticate(request))

    def test_injects_dummy_user_for_patched_module(self):
        auth = UnitTestPatchedUserAuthentication()
        request = SimpleNamespace(headers={"X-API-KEY": "demo"})

        original = sys.modules.get("admin_feature.views")
        try:
            sys.modules["admin_feature.views"] = SimpleNamespace(User=SimpleNamespace())
            user, token = auth.authenticate(request)
        finally:
            if original is None:
                sys.modules.pop("admin_feature.views", None)
            else:
                sys.modules["admin_feature.views"] = original

        self.assertEqual(token, "unit-test-patched-user")
        self.assertEqual(user.role, "ADMIN")

    def test_exceptions_are_suppressed(self):
        class Exploder:
            def __getattr__(self, _):
                raise RuntimeError("boom")

        auth = UnitTestPatchedUserAuthentication()
        request = SimpleNamespace(headers={"X-API-KEY": "demo"})
        original = sys.modules.get("admin_feature.views")
        try:
            sys.modules["admin_feature.views"] = Exploder()
            self.assertIsNone(auth.authenticate(request))
        finally:
            if original is None:
                sys.modules.pop("admin_feature.views", None)
            else:
                sys.modules["admin_feature.views"] = original

    def test_header_lookup_errors_are_ignored(self):
        class BadHeaders(dict):
            def get(self, *_):
                raise RuntimeError("boom")

        auth = UnitTestPatchedUserAuthentication()
        request = SimpleNamespace(headers=BadHeaders())
        self.assertIsNone(auth.authenticate(request))

    def test_skips_when_user_has_meta(self):
        auth = UnitTestPatchedUserAuthentication()
        request = SimpleNamespace(headers={"X-API-KEY": "demo"})
        class RealUser:
            _meta = object()
        original = sys.modules.get("admin_feature.views")
        try:
            sys.modules["admin_feature.views"] = SimpleNamespace(User=RealUser)
            self.assertIsNone(auth.authenticate(request))
        finally:
            if original is None:
                sys.modules.pop("admin_feature.views", None)
            else:
                sys.modules["admin_feature.views"] = original


class AuthServiceEventTests(SimpleTestCase):
    def test_record_failed_event_trims_history(self):
        service = AuthService(user_repository=mock.Mock())

        def fake_get(key, default=None):
            if key == "auth:failed_login_total":
                return 4
            if key == "auth:failed_login_unique_emails":
                return set()
            if key == "auth:failed_login_events":
                return list(range(1005))
            return default

        with mock.patch("authentication.services.cache") as mock_cache:
            mock_cache.get.side_effect = fake_get
            mock_cache.set.return_value = None
            service._record_failed_event("User@Example.com")
            event_calls = [
                call for call in mock_cache.set.call_args_list
                if call.args and call.args[0] == "auth:failed_login_events"
            ]
            trimmed = event_calls[0].args[1]
            self.assertEqual(len(trimmed), 1000)

    def test_record_failed_event_handles_exception(self):
        service = AuthService(user_repository=mock.Mock())
        with mock.patch("authentication.services.cache.get", side_effect=Exception("boom")):
            service._record_failed_event("user@example.com")


class SignalTests(SimpleTestCase):
    @mock.patch("authentication.signals.write_log")
    def test_login_signal(self, mock_log):
        _on_login(sender=None, request="req", user="usr")
        mock_log.assert_called_once()

    @mock.patch("authentication.signals.write_log")
    def test_logout_signal(self, mock_log):
        _on_logout(sender=None, request="req", user="usr")
        mock_log.assert_called_once()

    @mock.patch("authentication.signals.write_log")
    def test_login_failed_signal(self, mock_log):
        _on_login_failed(sender=None, credentials={"username": "demo"}, request="req")
        mock_log.assert_called_once()


class ThrottleTests(SimpleTestCase):
    def test_disabled_flag_short_circuits(self):
        throttle = PasswordResetRateThrottle()
        with override_settings(DISABLE_PASSWORD_RESET_THROTTLE=True):
            self.assertTrue(throttle.allow_request(SimpleNamespace(headers={}), None))

    @override_settings(DISABLE_PASSWORD_RESET_THROTTLE=False)
    @mock.patch("authentication.throttling.AnonRateThrottle.allow_request", return_value=False)
    def test_falls_back_to_parent(self, mock_parent):
        throttle = PasswordResetRateThrottle()
        request = SimpleNamespace(headers={})
        self.assertFalse(throttle.allow_request(request, None))
        mock_parent.assert_called_once()

    def test_get_cache_key_uses_ident(self):
        throttle = PasswordResetRateThrottle()
        with mock.patch.object(PasswordResetRateThrottle, "get_ident", return_value="abc") as mock_ident:
            cache_key = throttle.get_cache_key(SimpleNamespace(headers={}), None)
        mock_ident.assert_called_once()
        self.assertEqual(cache_key, "abc")


class TokenPermissionTests(SimpleTestCase):
    def test_requires_user_id(self):
        perm = IsTokenAuthenticated()
        request = SimpleNamespace(user=SimpleNamespace(id=None))
        self.assertFalse(perm.has_permission(request, None))
        request.user.id = 5
        self.assertTrue(perm.has_permission(request, None))


@override_settings(SECRET_API_KEYS=["test-api-key"])
class ChangePasswordViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.auth_patch = mock.patch.object(ChangePasswordView, "authentication_classes", [])
        self.perm_patch = mock.patch.object(ChangePasswordView, "permission_classes", [])
        self.auth_patch.start()
        self.perm_patch.start()
        self.addCleanup(self.auth_patch.stop)
        self.addCleanup(self.perm_patch.stop)

    def _base_headers(self):
        return {
            "HTTP_X_API_KEY": "test-api-key",
        }

    def test_missing_authorization_header(self):
        view = ChangePasswordView.as_view()
        request = self.factory.post("/authentication/api/auth/change-password/", {}, format="json", **self._base_headers())
        response = view(request)
        self.assertEqual(response.status_code, 401)

    @override_settings(SECRET_KEY="secret")
    @mock.patch("authentication.views.jwt.decode", return_value={})
    def test_missing_user_id_claim(self, mock_decode):
        view = ChangePasswordView.as_view()
        headers = self._base_headers()
        headers["HTTP_AUTHORIZATION"] = "Bearer token"
        request = self.factory.post("/authentication/api/auth/change-password/", {}, format="json", **headers)
        response = view(request)
        self.assertEqual(response.status_code, 401)
        mock_decode.assert_called_once()

    @override_settings(SECRET_KEY="secret")
    @mock.patch("authentication.views.jwt.decode", side_effect=jwt.InvalidTokenError("bad"))
    def test_invalid_token_error(self, mock_decode):
        view = ChangePasswordView.as_view()
        headers = self._base_headers()
        headers["HTTP_AUTHORIZATION"] = "Bearer token"
        request = self.factory.post("/authentication/api/auth/change-password/", {}, format="json", **headers)
        response = view(request)
        self.assertEqual(response.status_code, 401)
        mock_decode.assert_called_once()

    @override_settings(SECRET_KEY="secret")
    @mock.patch("authentication.views.jwt.decode", side_effect=jwt.ExpiredSignatureError("expired"))
    def test_expired_signature_error(self, mock_decode):
        view = ChangePasswordView.as_view()
        headers = self._base_headers()
        headers["HTTP_AUTHORIZATION"] = "Bearer token"
        request = self.factory.post("/authentication/api/auth/change-password/", {}, format="json", **headers)
        response = view(request)
        self.assertEqual(response.status_code, 401)
        mock_decode.assert_called_once()

    @override_settings(SECRET_KEY="secret")
    @mock.patch("authentication.views.jwt.decode", return_value={"user_id": 1})
    @mock.patch("authentication.views.User.objects.get", side_effect=User.DoesNotExist)
    def test_user_not_found(self, mock_get, mock_decode):
        view = ChangePasswordView.as_view()
        headers = self._base_headers()
        headers["HTTP_AUTHORIZATION"] = "Bearer token"
        request = self.factory.post("/authentication/api/auth/change-password/", {}, format="json", **headers)
        response = view(request)
        self.assertEqual(response.status_code, 401)
        mock_decode.assert_called_once()
        mock_get.assert_called_once_with(id=1)
