from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.views import SignupAPIView         
from pt_backend.models import User                      
from authentication.registration.service import RegistrationError


factory = APIRequestFactory()


class SignupAPIViewTests(TestCase):
    """Black-box tests for SignupAPIView (POST /signup)."""

    def _post(self, payload):
        """Utility to call the view and return the DRF Response."""
        request = factory.post("/signup/", payload, format="json")
        view = SignupAPIView.as_view()
        return view(request)

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

    def test_weak_password_returns_400(self):
        with patch(
            "authentication.registration.service.validate_password",
            side_effect=ValidationError("Too weak"),
        ):
            res = self._post(
                {"name": "Weak", "email": "weak@ex.com", "password": "123"}
            )
        self.assertEqual(res.status_code, 400)
        self.assertIn("password", res.data)

    def test_missing_password_returns_400(self):
        res = self._post({"name": "NoPwd", "email": "np@ex.com"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("password", res.data) 
