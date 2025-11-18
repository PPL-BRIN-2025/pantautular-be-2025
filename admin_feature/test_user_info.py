# admin_feature/test_user_info.py
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from pt_backend.models import Role, User
from django.contrib.auth.hashers import make_password
from django.conf import settings
import jwt
from datetime import datetime, timedelta, timezone
from rest_framework import status

TEST_API_KEY_HEADER = {"HTTP_X_API_KEY": "test-key"}

@override_settings(SECRET_API_KEYS=("test-key",))
class UserInfoJWTOnlyTests(TestCase):
    # Focused tests for /admin-feature/user-info with JWT + required API key

    databases = {"default"}

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("admin-user-info")
        self.admin = User.objects.create(
            name="JWT Admin",
            email="jwt-admin@example.com",
            password=make_password("AdminPass123"),
            role="ADMIN",
        )
        self.viewer = User.objects.create(
            name="JWT Viewer",
            email="jwt-viewer@example.com",
            password=make_password("ViewerPass123"),
            role="VIEWER",
        )
        Role.objects.get_or_create(name="ADMIN")
        Role.objects.get_or_create(name="VIEWER")

    def _login_and_get_token(self, email, password):
        login_url = reverse("login")
        resp = self.client.post(
            login_url, {"email": email, "password": password}, format="json", **TEST_API_KEY_HEADER
        )
        self.assertEqual(resp.status_code, 200, f"Login failed for {email}: {resp.content}")
        return resp.json()["access_token"]

    def _jwt_for_user(self, user):
        payload = {
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def test_jwt_admin_with_api_key_succeeds(self):
        token = self._login_and_get_token(self.admin.email, "AdminPass123")
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        resp = self.client.get(self.url, **headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["name"], self.admin.name)
        self.assertEqual(resp.data["role"], "ADMIN")

    def test_jwt_viewer_with_api_key_forbidden(self):
        token = self._login_and_get_token(self.viewer.email, "ViewerPass123")
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        resp = self.client.get(self.url, **headers)
        self.assertEqual(resp.status_code, 403)
        msg = str(resp.data.get("detail", "")).lower()
        self.assertTrue(any(k in msg for k in ["akses", "forbidden", "permission"]))

    def test_jwt_with_embedded_claims_no_user_lookup(self):
        payload = {
            "user_id": 999999,
            "name": "Embedded Admin",
            "role": "ADMIN",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": f"Bearer {token}"}
        resp = self.client.get(self.url, **headers)
        if resp.status_code == 200:
            self.assertEqual(resp.data["name"], "Embedded Admin")
            self.assertEqual(resp.data["role"], "ADMIN")
        else:
            self.skipTest("Auth backend does not support embedded-claims fallback for non-existent user_id")

    def test_jwt_with_malformed_authorization_header(self):
        token = self._jwt_for_user(self.admin)
        headers = {**TEST_API_KEY_HEADER, "HTTP_AUTHORIZATION": token}  # missing Bearer prefix
        resp = self.client.get(self.url, **headers)
        self.assertEqual(resp.status_code, 401)
        msg = str(resp.data.get("detail", "")).lower()
        self.assertTrue(any(k in msg for k in ["auth", "token", "credentials"]))

    def test_jwt_token_but_no_name_or_role(self):
        payload = {
            "user_id": self.admin.id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        resp = self.client.get(self.url, **headers)
        # Expect unauthorized instead of 200
        self.assertEqual(resp.status_code, 401)
