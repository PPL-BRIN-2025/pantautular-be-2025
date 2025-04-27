# authentication/tests/test_api_key_auth.py
import os
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.models import AnonymousUser

from authentication.security import APIKeyAuthentication


factory = APIRequestFactory()


class APIKeyAuthenticationTests(TestCase):

    def setUp(self):
        self.auth = APIKeyAuthentication()

    # ─────────────────────────── positive / happy path ────────────────────
    @override_settings(SECRET_API_KEYS=["foo", "bar"])
    def test_valid_key_returns_anonymous_user_and_key(self):
        request = factory.get("/", HTTP_X_API_KEY="bar")
        user, key = self.auth.authenticate(request)

        self.assertIsInstance(user, AnonymousUser)
        self.assertEqual(key, "bar")

    # ────────────────────────────── negative cases ────────────────────────
    @override_settings(SECRET_API_KEYS=["onlykey"])
    def test_missing_header_raises_authentication_failed(self):
        request = factory.get("/")
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.authenticate(request)
        self.assertEqual(str(ctx.exception), "API key missing.")

    @override_settings(SECRET_API_KEYS=["rightkey"])
    def test_invalid_key_raises_authentication_failed(self):
        request = factory.get("/", HTTP_X_API_KEY="wrongkey")
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.authenticate(request)
        self.assertEqual(str(ctx.exception), "Invalid API key.")

    # ─────────────────────────── corner / env-var fallback ────────────────
    def test_env_variable_key_is_accepted_when_settings_absent(self):
        os.environ["SECRET_API_KEY"] = "envkey"
        try:
            with override_settings(SECRET_API_KEYS=None):
                request = factory.get("/", HTTP_X_API_KEY="envkey")
                _, key = self.auth.authenticate(request)
                self.assertEqual(key, "envkey")
        finally:
            os.environ.pop("SECRET_API_KEY", None)  # clean up

    # ─────────────────────────── header helper string ─────────────────────
    def test_authenticate_header_returns_realm(self):
        header = self.auth.authenticate_header(factory.get("/"))
        self.assertEqual(header, 'X-API-KEY realm="api"')
