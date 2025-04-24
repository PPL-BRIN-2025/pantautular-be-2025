from django.test import TestCase
from django.db.utils import IntegrityError
from django.contrib.auth.hashers import check_password
from django.db import transaction
from pt_backend.models import (
    User,
    Role,
    Permission,
    UserRole,
    UserRoleRegistered,
    RolePermission,
)


class ModelTests(TestCase):
    def setUp(self):
        # ── base fixtures ────────────────────────────────────────────────────
        self.role_admin = Role.objects.create(name="ADMIN")
        self.role_member = Role.objects.create(name="MEMBER")
        self.user = User.objects.create(
            name="Ken Balya",
            password="plain-secret",  # NOSONAR – test data
            role="ADMIN",
            email="ken@example.com",
        )
        self.perm_read = Permission.objects.create(
            name="read_reports", description="Can read confidential reports"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # USER                                                                   │
    # ─────────────────────────────────────────────────────────────────────────
    def test_user_str_and_role_helpers(self):
        self.assertEqual(str(self.user), "Ken Balya")
        self.assertTrue(self.user.has_role("ADMIN"))
        self.assertFalse(self.user.has_role("MEMBER"))

    def test_update_password_hashes_and_persists(self):
        old_pw_hash = self.user.password
        self.user.update_password("new-secret")  # NOSONAR
        self.user.refresh_from_db()

        self.assertNotEqual(self.user.password, old_pw_hash)
        self.assertTrue(check_password("new-secret", self.user.password))

    def test_user_email_unique(self):
        with self.assertRaises(IntegrityError):
            User.objects.create(
                name="Clone",
                password="dup",  # NOSONAR
                role="MEMBER",
                email="ken@example.com",  # duplicate
            )

    # ─────────────────────────────────────────────────────────────────────────
    # ROLE & PERMISSION                                                      │
    # ─────────────────────────────────────────────────────────────────────────
    def test_role_and_permission_str_and_uniqueness(self):
        # ── str() checks ───────────────────────────
        self.assertEqual(str(self.role_admin), "ADMIN")
        self.assertEqual(str(self.perm_read), "read_reports")

        # ── duplicate ROLE should raise ────────────
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Role.objects.create(name="ADMIN")          # dup role

        # ── duplicate PERMISSION should raise ──────
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Permission.objects.create(
                    name="read_reports", description="dup"
                )

    # ─────────────────────────────────────────────────────────────────────────
    # RELATIONSHIP TABLES                                                    │
    # ─────────────────────────────────────────────────────────────────────────
    def test_user_role_unique_together(self):
        UserRole.objects.create(user=self.user, role=self.role_admin)
        with self.assertRaises(IntegrityError):
            UserRole.objects.create(user=self.user, role=self.role_admin)

    def test_role_permission_unique_together(self):
        RolePermission.objects.create(role=self.role_admin, permission=self.perm_read)
        with self.assertRaises(IntegrityError):
            RolePermission.objects.create(role=self.role_admin, permission=self.perm_read)

    # ─────────────────────────────────────────────────────────────────────────
    # REGISTERED ROLE META                                                   │
    # ─────────────────────────────────────────────────────────────────────────
    def test_registered_role_defaults_and_ordering(self):
        # default label = role.name
        reg_member = UserRoleRegistered.objects.create(role=self.role_member)
        self.assertEqual(reg_member.label, "MEMBER")
        self.assertEqual(str(reg_member), "MEMBER")

        # custom label, custom sort_order
        reg_admin = UserRoleRegistered.objects.create(
            role=self.role_admin, label="Administrator", sort_order=2
        )

        # ordering by sort_order then role__name
        ordered = list(UserRoleRegistered.objects.all())
        self.assertEqual(ordered, [reg_member, reg_admin])
