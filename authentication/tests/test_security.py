# authentication/tests/test_api_key_auth.py
import os
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.models import AnonymousUser

from authentication.security import APIKeyAuthentication, CustomJWTAuthentication


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

    def test_authentication_skips_when_flagged(self):
        request = factory.get("/")
        request._skip_api_key_auth = True

        self.assertIsNone(self.auth.authenticate(request))


class CustomJWTAuthenticationTests(TestCase):
    
    def setUp(self):
        self.auth = CustomJWTAuthentication()
        
        from pt_backend.models import User
        self.test_user = User.objects.create(
            email='test@example.com',
            password='password123',
            name='Test User',
            role='user'
        )

    def test_get_user_returns_correct_user(self):
        """Test that get_user returns the correct user when a valid token is provided"""
        mock_token = {'user_id': self.test_user.id}
        
        user = self.auth.get_user(mock_token)
        
        self.assertEqual(user.id, self.test_user.id)
        self.assertEqual(user.email, self.test_user.email)
        self.assertEqual(user.name, self.test_user.name)

    def test_get_user_raises_error_on_missing_user_id(self):
        """Test that get_user raises InvalidToken when user_id is missing in token"""
        mock_token = {'other_field': 'some_value'}
        
        from rest_framework_simplejwt.exceptions import InvalidToken
        with self.assertRaises(InvalidToken) as ctx:
            self.auth.get_user(mock_token)
        
        self.assertEqual(
            ctx.exception.detail['detail'], 
            'Token contained no recognizable user identification'
        )

    def test_get_user_raises_error_on_nonexistent_user(self):
        """Test that get_user raises AuthenticationFailed when user does not exist"""
        mock_token = {'user_id': 99999}
        
        from rest_framework.exceptions import AuthenticationFailed
        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.get_user(mock_token)
        
        self.assertEqual(str(ctx.exception), 'User not found')
        self.assertEqual(ctx.exception.code, 'user_not_found')

    def test_get_user_handles_database_error(self):
        """Test that get_user gracefully handles database errors"""
        mock_token = {'user_id': self.test_user.id}
        
        from pt_backend.models import User
        from unittest.mock import patch
        with patch.object(User.objects, 'get', side_effect=Exception('Database connection error')):
            from rest_framework.exceptions import AuthenticationFailed
            with self.assertRaises(AuthenticationFailed) as ctx:
                self.auth.get_user(mock_token)
            
            self.assertEqual(str(ctx.exception), 'Error finding user: Database connection error')

    def tearDown(self):
        self.test_user.delete()
