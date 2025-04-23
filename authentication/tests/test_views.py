from unittest.mock import patch
from django.urls import reverse
from rest_framework.test import APIClient
import os
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory
from authentication.views import SignupAPIView
from pt_backend.models import User

client = APIClient()


@override_settings(SECRET_API_KEYS=["testkey"])          
class SignupAPIViewTests(TestCase):
    """Black-box tests for the sign-up endpoint secured by API-key auth."""

    def _post(self, payload, api_key="testkey"):
        """
        POST to the real URL resolved by its name (`sign-up`) so changes
        in urls.py never break the tests.
        """
        url = reverse("sign-up")              
        return client.post(
            url,
            payload,
            format="json",
            HTTP_X_API_KEY=api_key,
        )

    def test_signup_happy_path(self):
        res = self._post(
            {"name": "Ken", "email": "ken@example.com", "password": "5up3rSafe!"}
        )

        self.assertEqual(res.status_code, 201)
        self.assertTrue(
            User.objects.filter(id=res.data["id"], email="ken@example.com").exists()
        )

    def test_duplicate_email_returns_400(self):
        self._post(
            {"name": "Ken", "email": "dup@ex.com", "password": "Sup3rSafe!"}
        )

        res = self._post(
            {"name": "Clone", "email": "dup@ex.com", "password": "OtherSafe12!"}
        )

        self.assertEqual(res.status_code, 400)
        self.assertIn("already exists", res.data["detail"])

    def test_service_rejects_password_returns_400(self):
        """
        Password passes serializer (>8 chars) but RegistrationService vetoes it.
        """
        with patch(
            "authentication.registration.service.validate_password",
            side_effect=ValidationError("Too weak"),
        ):
            res = self._post(
                {"name": "Weak", "email": "weak@ex.com", "password": "WeakPass1"}
            )

        self.assertEqual(res.status_code, 400)
        self.assertIn("Too weak", res.data["detail"])

    def test_missing_password_returns_400(self):
        res = self._post({"name": "NoPwd", "email": "np@ex.com"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("password", res.data)

    def test_missing_or_wrong_api_key_returns_401(self):
        res = self._post(
            {"name": "Ken", "email": "wrongkey@ex.com", "password": "5up3rSafe!"},
            api_key="badkey",
        )
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid API key", res.data["detail"])
