# tests/test_models.py
from django.test import TestCase
from django.db.utils import IntegrityError
from django.contrib.auth.hashers import check_password

from pt_backend.models import (          # replace `your_app` with the real app name
    User,
    Role,
    Permission,
    UserRole,
    UserRoleRegistered,
    RolePermission,
)


class ModelTests(TestCase):
    """Unit-tests for User / Role / Permission and the relationship helpers."""

    def setUp(self) -> None:
        self.role_admin  = Role.objects.create(name="ADMIN")
        self.role_member = Role.objects.create(name="MEMBER")

        self.user = User.objects.create(
            name="Ken Balya",
            password="plain-secret", # NOSONAR – test data, not a real secret
            role="ADMIN",
            email="ken@example.com",
        )
        self.perm_read = Permission.objects.create(
            name="read_reports", description="Can read confidential reports"
        )

    def test_user_str_returns_name(self):
        self.assertEqual(str(self.user), "Ken Balya")

    def test_user_has_role(self):
        self.assertTrue(self.user.has_role("ADMIN"))
        self.assertFalse(self.user.has_role("MEMBER"))

    def test_update_password_hashes_and_persists(self):
        self.user.update_password("new-secret")
        self.user.refresh_from_db()
        # password has been hashed & stored:
        self.assertNotEqual(self.user.password, "new-secret") # NOSONAR – test data, not a real secret
        self.assertTrue(check_password("new-secret", self.user.password)) # NOSONAR – test data, not a real secret

    def test_user_email_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            User.objects.create(
                name="Clone",
                password="whatever", # NOSONAR – test data, not a real secret
                role="MEMBER",
                email="ken@example.com",  
            )

    def test_role_str(self):
        self.assertEqual(str(self.role_admin), "ADMIN")

    def test_role_name_unique(self):
        with self.assertRaises(IntegrityError):
            Role.objects.create(name="ADMIN")  


    def test_permission_str(self):
        self.assertEqual(str(self.perm_read), "read_reports")

    def test_permission_name_unique(self):
        with self.assertRaises(IntegrityError):
            Permission.objects.create(
                name="read_reports", description="dup"
            )


    def test_user_role_unique_together(self):
        UserRole.objects.create(user=self.user, role=self.role_admin)
        # second insert of the same pair should fail
        with self.assertRaises(IntegrityError):
            UserRole.objects.create(user=self.user, role=self.role_admin)


    def test_registered_role_defaults_label_to_role_name(self):
        reg = UserRoleRegistered.objects.create(role=self.role_member)
        self.assertEqual(reg.label, "MEMBER")
        self.assertEqual(str(reg), "MEMBER")

    def test_registered_role_ordering(self):
        r1 = UserRoleRegistered.objects.create(role=self.role_admin, sort_order=2)
        r2 = UserRoleRegistered.objects.create(role=self.role_member, sort_order=1)
        self.assertListEqual(
            list(UserRoleRegistered.objects.all()), [r2, r1]
        )


    def test_role_permission_unique_together(self):
        RolePermission.objects.create(role=self.role_admin, permission=self.perm_read)
        with self.assertRaises(IntegrityError):
            RolePermission.objects.create(
                role=self.role_admin, permission=self.perm_read
            )
