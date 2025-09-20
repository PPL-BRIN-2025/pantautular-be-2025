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

    def test_list_users_unauthorized(self):
        # no Authorization header
        client = APIClient()
        res = client.get("/admin-feature/users")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_users_forbidden_non_admin(self):
        # non-admin token
        non_admin = User.objects.create(
            name="Bob", email="bob@example.com", password="pass123", role="Contributor"
        )
        UserRole.objects.create(user=non_admin, role=self.contributor)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {make_access_token(non_admin)}")
        res = client.get("/admin-feature/users")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_change_role_invalid_role_name(self):
        res = self.client.put(
            f"/admin-feature/users/{self.alice.id}/role",
            {"role_name": "NotARole"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_role_missing_body(self):
        res = self.client.put(
            f"/admin-feature/users/{self.alice.id}/role", {}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_role_user_not_found(self):
        res = self.client.put(
            "/admin-feature/users/999999/role", {"role_name": "Curator"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_change_role_idempotent_same_role(self):
        # Set Alice to Curator first
        self.client.put(
            f"/admin-feature/users/{self.alice.id}/role",
            {"role_name": "Curator"},
            format="json",
        )
        # Change to Curator again
        res = self.client.put(
            f"/admin-feature/users/{self.alice.id}/role",
            {"role_name": "Curator"},
            format="json",
        )
        self.assertIn(res.status_code, (status.HTTP_200_OK, status.HTTP_304_NOT_MODIFIED))
        # Still only one UserRole row to Curator
        self.assertTrue(UserRole.objects.filter(user=self.alice, role=self.curator).exists())
        self.assertEqual(UserRole.objects.filter(user=self.alice).count(), 1)

    def test_delete_user_not_found(self):
        res = self.client.delete("/admin-feature/users/999999")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_user_forbidden_non_admin(self):
        non_admin = User.objects.create(
            name="Bob2", email="bob2@example.com", password="pass123", role="Contributor"
        )
        UserRole.objects.create(user=non_admin, role=self.contributor)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {make_access_token(non_admin)}")
        res = client.delete(f"/admin-feature/users/{self.alice.id}")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_self_allowed(self):
        res = self.client.delete(f"/admin-feature/users/{self.admin.id}")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.admin.id).exists())



