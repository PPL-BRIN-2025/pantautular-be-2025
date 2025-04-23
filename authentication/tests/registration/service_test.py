# tests/test_registration_service.py
from unittest.mock import patch

from django.test import TestCase
from django.core.exceptions import ValidationError

from ...registration.service import RegistrationService, RegistrationError
from ...registration import get_factory                    # to prep fixtures
from pt_backend.models import Role, Permission, UserRole   # replace `your_app`


class RegistrationServiceTests(TestCase):
    """Covers success & failure scenarios of the service layer."""

    def setUp(self) -> None:
        # Ensure the Tenaga Ahli factory is present (auto-import should handle)
        self.factory = get_factory("TENAGA_AHLI")

    # ------------------------------------------------------------------ happy
    def test_register_tenaga_ahli_success(self):
        dto = RegistrationService.register_user(
            role_name="TENAGA_AHLI",
            name="Dr. Rahma",
            email="rahma@corp.id",
            password="Sup3rSafe!",
        )

        self.assertEqual(dto.user.email, "rahma@corp.id")
        self.assertEqual(dto.role.name, "TENAGA_AHLI")

        # Role linked through bridge table
        self.assertTrue(
            UserRole.objects.filter(user=dto.user, role=dto.role).exists()
        )

        # Permissions created & attached
        self.assertSetEqual(
            set(dto.role.permissions.values_list("permission__name", flat=True)),
            {"submit_report", "view_dashboard"},
        )

        # Welcome-email hook executed (we patch it below in failure tests)

    # -------------------------------------------------------------- duplicates
    def test_duplicate_email_raises_error(self):
        RegistrationService.register_user(
            role_name="TENAGA_AHLI",
            name="First",
            email="dup@example.com",
            password="Sup3rSafe!",
        )

        with self.assertRaises(RegistrationError) as ctx:
            RegistrationService.register_user(
                role_name="TENAGA_AHLI",
                name="Second",
                email="dup@example.com",        # duplicate
                password="AnotherSafe123!",
            )
        self.assertIn("already exists", str(ctx.exception))

    # ---------------------------------------------------------------- unknown
    def test_unknown_role_raises_error(self):
        with self.assertRaises(RegistrationError):
            RegistrationService.register_user(
                role_name="NON_EXISTENT",
                name="Ghost",
                email="ghost@void.id",
                password="Sup3rSafe!",
            )

    # ------------------------------------------------------------ weak passpw
    def test_weak_password_raises_error(self):
        # Patch Django's validator to simulate rejection
        with patch(
            "authentication.registration.service.validate_password",
            side_effect=ValidationError("Too weak"),
        ):
            with self.assertRaises(RegistrationError) as ctx:
                RegistrationService.register_user(
                    role_name="TENAGA_AHLI",
                    name="Weakling",
                    email="weak@corp.id",
                    password="123",
                )
            self.assertIn("Too weak", str(ctx.exception))
