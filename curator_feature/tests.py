from uuid import uuid4

from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.test import override_settings
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from curator_feature.models import BackendCase

class CuratorCasesAPITest(APITestCase):
    def setUp(self):
        self.group_curator, _ = Group.objects.get_or_create(name="CURATOR")

        self.curator = User.objects.create_user(
            username="curator@example.com",
            password="curatorpass123",
            email="curator@example.com",
        )
        self.curator.groups.add(self.group_curator)

        self.non_curator = User.objects.create_user(
            username="normal@example.com",
            password="normalpass123",
            email="normal@example.com",
        )

        self.case_a = BackendCase.objects.create(
            id=uuid4(), gender="female", age=25, city="Jakarta",
            status="active", disease_id=uuid4(), location_id=uuid4(), severity="high"
        )
        self.case_b = BackendCase.objects.create(
            id=uuid4(), gender="male", age=30, city="Bandung",
            status="recovered", disease_id=uuid4(), location_id=uuid4(), severity="low"
        )

        self.client = APIClient()
        self.url = reverse("curator_cases_list")

    def auth_as(self, user):
        """Authenticate the APIClient as `user` without hitting JWT endpoints."""
        self.client.force_authenticate(user=user)

    def unauth(self):
        """Clear any forced authentication."""
        self.client.force_authenticate(user=None)

    def test_unauthenticated_cannot_access(self):
        self.unauth()
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_curator_forbidden(self):
        self.auth_as(self.non_curator)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_curator_can_access_and_get_data(self):
        self.auth_as(self.curator)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("data", res.data)
        self.assertIn("total", res.data)
        self.assertGreaterEqual(res.data["total"], 2)

    def test_pagination_and_filters(self):
        self.auth_as(self.curator)

        res = self.client.get(self.url + "?page=1&pageSize=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["page"], 1)
        self.assertEqual(res.data["pageSize"], 1)

        res = self.client.get(self.url + "?search=Jakarta")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any("Jakarta" in c["city"] for c in res.data["data"]))

        res = self.client.get(self.url + "?gender=female&status=active&severity=high")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(c["gender"] == "female" for c in res.data["data"]))

    def test_age_filter_and_sorting(self):
        self.auth_as(self.curator)

        res = self.client.get(self.url + "?minAge=20&maxAge=26&sort=age:desc")
        self.assertEqual(res.status_code, 200)
        ages = [c["age"] for c in res.data["data"]]
        self.assertTrue(all(20 <= a <= 26 for a in ages))
        if len(ages) > 1:
            self.assertGreaterEqual(ages[0], ages[-1])

    def test_invalid_sort_fallback(self):
        self.auth_as(self.curator)
        res = self.client.get(self.url + "?sort=unknown:asc")
        self.assertEqual(res.status_code, 200)
        self.assertIn("data", res.data)

    def test_filter_by_location_id(self):
        self.auth_as(self.curator)
        res = self.client.get(self.url + f"?location_id={self.case_a.location_id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            all(str(c["location_id"]) == str(self.case_a.location_id)
                for c in res.data["data"])
        )

    def test_filter_min_age_only(self):
        self.auth_as(self.curator)
        res = self.client.get(self.url + "?minAge=26")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(c["age"] >= 26 for c in res.data["data"]))

    def test_filter_max_age_only(self):
        self.auth_as(self.curator)
        res = self.client.get(self.url + "?maxAge=26")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(c["age"] <= 26 for c in res.data["data"]))
        
    def test_filter_by_disease_id(self):
        self.auth_as(self.curator)
        res = self.client.get(self.url + f"?disease_id={self.case_a.disease_id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            all(str(c["disease_id"]) == str(self.case_a.disease_id)
                for c in res.data["data"])
        )

# additional tests to test for the permission policy

class CuratorPermissionPolicyTest(APITestCase):
    """
    TDD for curator access policy:
    - Allow by role attribute
    - Allow by Django Group
    - Role name and check strategy are configurable via settings
    """

    def setUp(self):
        self.grp_curator, _ = Group.objects.get_or_create(name="CURATOR")
        self.grp_kurator, _ = Group.objects.get_or_create(name="KURATOR")

        # role-only user (no group)
        self.user_role_only = User.objects.create_user(
            username="roleonly@example.com", password="pw", email="roleonly@example.com"
        )
        setattr(self.user_role_only, "role", "CURATOR")
        self.user_role_only.save()

        # group-only user (no role)
        self.user_group_only = User.objects.create_user(
            username="grouponly@example.com", password="pw", email="grouponly@example.com"
        )
        self.user_group_only.groups.add(self.grp_curator)

        # plain user
        self.user_plain = User.objects.create_user(
            username="plain@example.com", password="pw", email="plain@example.com"
        )

        # minimal data for list endpoint
        BackendCase.objects.create(
            id=uuid4(), gender="female", age=21, city="Depok",
            status="active", disease_id=uuid4(), location_id=uuid4(), severity="low"
        )

        self.client = APIClient()
        self.url = reverse("curator_cases_list")

    def auth_as(self, user):
        self.client.force_authenticate(user=user)

    def unauth(self):
        self.client.force_authenticate(user=None)

    @override_settings(CURATOR_ROLE_NAME="CURATOR", CURATOR_ROLE_CHECKS=("role", "group"))
    def test_role_attribute_allows_access(self):
        self.auth_as(self.user_role_only)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @override_settings(CURATOR_ROLE_NAME="CURATOR", CURATOR_ROLE_CHECKS=("role", "group"))
    def test_group_membership_allows_access(self):
        self.auth_as(self.user_group_only)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @override_settings(CURATOR_ROLE_NAME="CURATOR", CURATOR_ROLE_CHECKS=("role", "group"))
    def test_plain_user_forbidden(self):
        self.auth_as(self.user_plain)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(CURATOR_ROLE_NAME="KURATOR", CURATOR_ROLE_CHECKS=("role", "group"))
    def test_changed_role_name_is_respected(self):
        setattr(self.user_role_only, "role", "KURATOR")
        self.user_role_only.save()

        self.auth_as(self.user_role_only)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        user_group_kurator = User.objects.create_user(
            username="gkurator@example.com", password="pw", email="gkurator@example.com"
        )
        user_group_kurator.groups.add(self.grp_kurator)
        self.auth_as(user_group_kurator)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @override_settings(CURATOR_ROLE_NAME="CURATOR", CURATOR_ROLE_CHECKS=("role",))
    def test_checks_role_only_denies_group_only_user(self):
        self.auth_as(self.user_group_only)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        self.auth_as(self.user_role_only)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @override_settings(CURATOR_ROLE_NAME="CURATOR", CURATOR_ROLE_CHECKS=("group",))
    def test_checks_group_only_denies_role_only_user(self):
        self.auth_as(self.user_role_only)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        self.auth_as(self.user_group_only)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_unauthenticated_is_401(self):
        self.unauth()
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)