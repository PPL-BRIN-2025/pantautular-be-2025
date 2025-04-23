from django.test import TestCase
from authentication.registration import get_factory
from pt_backend.models import Role, Permission, UserRole


class TenagaAhliRegistrationTests(TestCase):
    def test_register_tenaga_ahli_happy_path(self):
        factory = get_factory("tenaga_ahli")   # case-insensitive

        dto = factory.register(
            name="Dr. Rahma",
            email="rahma@corp.id",
            raw_password="Sup3rSafe!",
        )

        self.assertEqual(dto.role.name, "TENAGA_AHLI")
        self.assertEqual(dto.user.email, "rahma@corp.id")

        self.assertTrue(
            UserRole.objects.filter(user=dto.user, role=dto.role).exists()
        )

        expected = {"submit_report", "view_dashboard"}

        self.assertSetEqual(
            set(dto.role.permissions.values_list("permission__name", flat=True)),
            expected,
        )


        self.assertEqual(Role.objects.filter(name="TENAGA_AHLI").count(), 1)

        self.assertEqual(str(dto), "Dr. Rahma (TENAGA_AHLI)")
