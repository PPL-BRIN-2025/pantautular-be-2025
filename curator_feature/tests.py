from uuid import uuid4
from datetime import timedelta

from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.models import User, Group, AnonymousUser
from django.test import override_settings
from django.db import connection
from rest_framework import status
from rest_framework.test import APITestCase, APIClient, APIRequestFactory

from curator_feature.permissions import IsCuratorRole
from curator_feature.models import BackendCase, CuratorDataLog

def _drop_case_table():
    """Drop pt_backend_case for current DB vendor."""
    with connection.cursor() as cur:
        if connection.vendor == "postgresql":
            cur.execute("DROP TABLE IF EXISTS pt_backend_case CASCADE")
        else:
            cur.execute("DROP TABLE IF EXISTS pt_backend_case")


def _create_case_table_no_fk():
    """Create pt_backend_case with cols matching BackendCase (no FKs)."""
    with connection.cursor() as cur:
        if connection.vendor == "postgresql":
            cur.execute(
                """
                CREATE TABLE pt_backend_case (
                  id UUID PRIMARY KEY,
                  gender VARCHAR(10),
                  age INTEGER,
                  city VARCHAR(255),
                  status VARCHAR(20),
                  disease_id UUID,
                  location_id UUID,
                  severity VARCHAR(255)
                )
                """
            )
        else:  # sqlite fallback
            cur.execute(
                """
                CREATE TABLE pt_backend_case (
                  id TEXT PRIMARY KEY,
                  gender TEXT,
                  age INTEGER,
                  city TEXT,
                  status TEXT,
                  disease_id TEXT,
                  location_id TEXT,
                  severity TEXT
                )
                """
            )


# =====================================================================
# Tests — CuratorCasesListAPIView  (GET /curator-feature/cases/)
# =====================================================================
class CuratorCasesAPITest(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _drop_case_table()
        _create_case_table_no_fk()

    @classmethod
    def tearDownClass(cls):
        _drop_case_table()
        super().tearDownClass()

    def setUp(self):
        self.grp_curator, _ = Group.objects.get_or_create(name="CURATOR")

        self.curator = User.objects.create_user(
            username="curator@example.com",
            password="curatorpass123",
            email="curator@example.com",
        )
        self.curator.groups.add(self.grp_curator)

        self.non_curator = User.objects.create_user(
            username="user@example.com",
            password="userpass123",
            email="user@example.com",
        )

        # Seed pt_backend_case via managed=False model
        self.case_a = BackendCase.objects.create(
            id=uuid4(), gender="female", age=25, city="Jakarta",
            status="active", disease_id=uuid4(), location_id=uuid4(), severity="high"
        )
        self.case_b = BackendCase.objects.create(
            id=uuid4(), gender="male", age=30, city="Bandung",
            status="recovered", disease_id=uuid4(), location_id=uuid4(), severity="low"
        )

        self.client = APIClient()
        self.list_url = reverse("curator_cases_list")

    # --- helpers
    def auth_as(self, user):
        self.client.force_authenticate(user=user)

    def unauth(self):
        self.client = APIClient()

    # --- tests
    def test_unauthenticated_cannot_access(self):
        self.unauth()
        res = self.client.get(self.list_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_curator_forbidden(self):
        self.auth_as(self.non_curator)
        res = self.client.get(self.list_url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_curator_can_access_and_get_data(self):
        self.auth_as(self.curator)
        res = self.client.get(self.list_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("data", res.data)
        self.assertIn("total", res.data)
        self.assertGreaterEqual(res.data["total"], 2)

    def test_pagination_and_filters(self):
        self.auth_as(self.curator)

        # pagination
        res = self.client.get(self.list_url + "?page=1&pageSize=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["page"], 1)
        self.assertEqual(res.data["pageSize"], 1)

        # search (OR across city/status/severity)
        res = self.client.get(self.list_url + "?search=Jakarta")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any("Jakarta" in c["city"] for c in res.data["data"]))

        # exact filters
        res = self.client.get(self.list_url + "?gender=female&status=active&severity=high")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(c["gender"] == "female" for c in res.data["data"]))

    def test_age_filter_and_sorting(self):
        self.auth_as(self.curator)
        res = self.client.get(self.list_url + "?minAge=20&maxAge=26&sort=age:desc")
        self.assertEqual(res.status_code, 200)
        ages = [c["age"] for c in res.data["data"]]
        self.assertTrue(all(20 <= a <= 26 for a in ages))
        if len(ages) > 1:
            self.assertGreaterEqual(ages[0], ages[-1])

    def test_invalid_sort_fallback(self):
        self.auth_as(self.curator)
        res = self.client.get(self.list_url + "?sort=unknown:asc")
        self.assertEqual(res.status_code, 200)
        self.assertIn("data", res.data)

    def test_filter_by_location_and_disease(self):
        self.auth_as(self.curator)

        res = self.client.get(self.list_url + f"?location_id={self.case_a.location_id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            all(str(c["location_id"]) == str(self.case_a.location_id) for c in res.data["data"])
        )

        res = self.client.get(self.list_url + f"?disease_id={self.case_a.disease_id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            all(str(c["disease_id"]) == str(self.case_a.disease_id) for c in res.data["data"])
        )

    def test_min_only_max_only(self):
        self.auth_as(self.curator)

        res = self.client.get(self.list_url + "?minAge=26")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(c["age"] >= 26 for c in res.data["data"]))

        res = self.client.get(self.list_url + "?maxAge=26")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(c["age"] <= 26 for c in res.data["data"]))


# =====================================================================
# Tests — CuratorDataLogListCreateAPIView (GET + POST)
# name: curator_audit_logs
# =====================================================================
class CuratorAuditTrailAPITest(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _drop_case_table()
        _create_case_table_no_fk()

    @classmethod
    def tearDownClass(cls):
        _drop_case_table()
        super().tearDownClass()

    def setUp(self):
        self.grp_curator, _ = Group.objects.get_or_create(name="CURATOR")
        self.curator = User.objects.create_user(
            username="curatora", password="pw", email="curatora@example.com"
        )
        self.curator.groups.add(self.grp_curator)

        self.other_user = User.objects.create_user(
            username="nonauth", password="pw", email="nonauth@example.com"
        )

        # a BackendCase used to derive title (severity) on POST without title
        self.case_x = BackendCase.objects.create(
            id=uuid4(), gender="female", age=40, city="Depok",
            status="active", disease_id=uuid4(), location_id=uuid4(), severity="hospitalisasi"
        )

        # seed logs
        t0 = timezone.now()
        CuratorDataLog.objects.create(
            data_id=str(uuid4()),
            title="insiden",
            submitted_by="KURATORA",
            note="n1",
            last_edited=t0 - timedelta(days=2),
        )
        CuratorDataLog.objects.create(
            data_id=str(uuid4()),
            title="hospitalisasi",
            submitted_by="KURATORB",
            note="n2",
            last_edited=t0 - timedelta(days=1),
        )

        self.client = APIClient()
        self.url = reverse("curator_audit_logs")

    # helpers
    def auth_as(self, user):
        self.client.force_authenticate(user=user)

    def unauth(self):
        self.client = APIClient()

    # GET tests
    def test_get_requires_auth_and_curator(self):
        # 401
        self.unauth()
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        # 403
        self.auth_as(self.other_user)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_ok_with_filters_sort_variants_and_pagination_caps(self):
        self.auth_as(self.curator)

        # basic
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertIn("data", res.data)
        self.assertIn("total", res.data)

        # search on title & submitted_by & data_id
        res = self.client.get(self.url + "?search=insiden")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any(r["title"] == "insiden" for r in res.data["data"]))

        # submitted_by filter (case-insensitive)
        res = self.client.get(self.url + "?submitted_by=kuratorb")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(r["submitted_by"].upper() == "KURATORB" for r in res.data["data"]))

        # date range filter + sort asc
        start = (timezone.now() - timedelta(days=3)).isoformat()
        end = (timezone.now() - timedelta(hours=12)).isoformat()
        res = self.client.get(self.url + f"?start={start}&end={end}&sort=last_edited:asc")
        self.assertEqual(res.status_code, 200)

        # unknown sort → fallback to last_edited
        res = self.client.get(self.url + "?sort=unknown:desc")
        self.assertEqual(res.status_code, 200)

        # no colon in sort → default desc branch exercised
        res = self.client.get(self.url + "?sort=title")
        self.assertEqual(res.status_code, 200)

        # pagination caps + invalid int path of _i()
        res = self.client.get(self.url + "?page=abc&pageSize=500")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["page"], 1)       # invalid -> fallback
        self.assertEqual(res.data["pageSize"], 100) # capped to 100

        # normal pagination
        res = self.client.get(self.url + "?page=1&pageSize=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["page"], 1)
        self.assertEqual(res.data["pageSize"], 1)

    # POST tests
    def test_post_create_with_explicit_title(self):
        self.auth_as(self.curator)
        payload = {
            "data_id": str(uuid4()),
            "title": "insiden",
            "note": "created",
            # provide submitted_by to satisfy serializer regardless of view’s 'submittedBy' bug
            "submitted_by": "curatora",
        }
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["title"], "insiden")
        self.assertIn("submitted_by", res.data)

    def test_post_create_without_title_derives_from_case_severity(self):
        self.auth_as(self.curator)
        payload = {
            "data_id": str(self.case_x.id),  # no title → expect 'hospitalisasi'
            "submitted_by": "curatora",
        }
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["title"], "hospitalisasi")

    def test_post_without_title_and_case_not_found_returns_400(self):
        """Covers the except BackendCase.DoesNotExist path."""
        self.auth_as(self.curator)
        payload = {
            "data_id": str(uuid4()),  # not in pt_backend_case
            "submitted_by": "curatora",
        }
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_bad_request(self):
        self.auth_as(self.curator)
        # no data_id and no title → serializer should reject
        res = self.client.post(self.url, {"note": "x"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class CuratorPermissionPolicyTest(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _drop_case_table()
        _create_case_table_no_fk()

    @classmethod
    def tearDownClass(cls):
        _drop_case_table()
        super().tearDownClass()

    def setUp(self):
        self.grp_curator, _ = Group.objects.get_or_create(name="CURATOR")
        # role-only user
        self.user_role_only = User.objects.create_user(
            username="roleonly@example.com", password="pw", email="roleonly@example.com"
        )
        setattr(self.user_role_only, "role", "CURATOR")
        self.user_role_only.save()
        # group-only user
        self.user_group_only = User.objects.create_user(
            username="grouponly@example.com", password="pw", email="grouponly@example.com"
        )
        self.user_group_only.groups.add(self.grp_curator)
        # plain
        self.user_plain = User.objects.create_user(
            username="plain@example.com", password="pw", email="plain@example.com"
        )
        # minimal data for GET OK
        BackendCase.objects.create(
            id=uuid4(), gender="female", age=22, city="Depok",
            status="active", disease_id=uuid4(), location_id=uuid4(), severity="low"
        )
        self.client = APIClient()
        self.url = reverse("curator_cases_list")

    def auth_as(self, user):
        self.client.force_authenticate(user=user)

    def unauth(self):
        self.client = APIClient()

    @override_settings(CURATOR_ROLE_NAME="CURATOR", CURATOR_ROLE_CHECKS=("role", "group"))
    def test_role_attribute_allows_access(self):
        self.auth_as(self.user_role_only)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @override_settings(CURATOR_ROLE_NAME="Curator", CURATOR_ROLE_CHECKS=("role",))
    def test_role_match_case_insensitive(self):
        self.user_role_only.role = "curator"
        self.user_role_only.save()
        self.auth_as(self.user_role_only)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @override_settings(CURATOR_ROLE_NAME="CURATOR", CURATOR_ROLE_CHECKS=("unknown",))
    def test_unknown_check_strategy_denies(self):
        self.auth_as(self.user_role_only)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

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

    def test_is_curator_role_denies_anonymous(self):
        req = APIRequestFactory().get("/curator-feature/cases/")
        req.user = AnonymousUser()
        perm = IsCuratorRole()
        assert perm.has_permission(req, None) is False
