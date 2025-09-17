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

