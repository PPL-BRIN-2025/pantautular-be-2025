import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pantau_tular.test_settings")

import django
django.setup()
from datetime import date, datetime
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone
from django.db import DatabaseError
from rest_framework.test import APITestCase, APIClient, APIRequestFactory
from rest_framework import serializers, status
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch
from django.test import override_settings, SimpleTestCase, TestCase
from django.urls import reverse

from curator_feature.models import DownloadLog, DashboardDownloadEvent
from uuid import uuid4
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from django.test import override_settings
from django.db import connection
from rest_framework import status
from rest_framework.test import APITestCase, APIClient, APIRequestFactory
# app models (pt_backend)
from pt_backend.models import Case, Disease, Location, News, User as PtUser
# django auth
from django.contrib.auth.models import User as DjangoUser, Group, AnonymousUser

from curator_feature.permissions import IsCuratorRole
from curator_feature.models import BackendCase, CuratorDataLog

from curator_feature.serializers import (
    CaseInsensitiveChoiceField,
    ChartDataFiltersSerializer,
    DashboardDownloadEventSerializer,
    DownloadLogRequestSerializer,
    DownloadLogResponseSerializer,
)
from curator_feature.services import ChartDataService, DashboardDownloadEventService, DownloadLogService
from curator_feature.views import (
    ChartDataAPIView,
    DashboardDownloadEventAPIView,
    DownloadLogAPIView,
    ChartsSimpleView,
)
from curator_feature.value_objects import ClientMetadata


class ChartsSimpleViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_returns_chart_payload(self):
        class DummyService:
            def get_chart_data(self):
                return {"charts": {"foo": "bar"}}

        with patch.object(ChartsSimpleView, "service_class", DummyService):
            response = ChartsSimpleView.as_view()(self.factory.get("/charts/simple"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["charts"]["foo"], "bar")

    def test_handles_service_error(self):
        class FailingService:
            def get_chart_data(self):
                raise RuntimeError("boom")

        with patch.object(ChartsSimpleView, "service_class", FailingService):
            response = ChartsSimpleView.as_view()(self.factory.get("/charts/simple"))

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["message"], "Failed to fetch chart data")


from django.utils import timezone
from django.db.utils import InternalError
from admin_feature.models import AdminUserLog
from admin_feature.audittrail import write_log
from django.test import TestCase

from curator_feature.models import BackendCase

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

        self.curator = DjangoUser.objects.create_user(
            username="curator@example.com",
            password="curatorpass123",
            email="curator@example.com",
        )
        self.curator.groups.add(self.grp_curator)

        self.non_curator = DjangoUser.objects.create_user(
            username="user@example.com",
            password="userpass123",
            email="user@example.com",
        )

        # Adding a Jakarta row used later by tests (self.case_a)
        self.case_a = BackendCase.objects.create(
            id=uuid4(), gender="female", age=25, city="Jakarta",
            status="active", disease_id=uuid4(), location_id=uuid4(), severity="high"
        )

        self.case_b = BackendCase.objects.create(
            id=uuid4(), gender="male", age=30, city="Bandung",
            status="recovered", disease_id=uuid4(), location_id=uuid4(), severity="low"
        )

        BackendCase.objects.create(
            id=uuid4(), gender="female", age=22, city="Depok",
            status="active", disease_id=uuid4(), location_id=uuid4(), severity="low"
        )
        
        self.url = reverse("curator_cases_list")

    # --- helpers
    def auth_as(self, user):
        self.client.force_authenticate(user=user)

    def unauth(self):
        self.client = APIClient()

    # --- tests
    def test_unauthenticated_cannot_access(self):
        self.unauth()
        res = self.client.get(self.url)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_curator_forbidden(self):
        self.auth_as(self.non_curator)
        res = self.client.get(self.url)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_curator_can_access_and_get_data(self):
        self.auth_as(self.curator)
        res = self.client.get(self.url)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("data", res.data)
        self.assertIn("total", res.data)
        self.assertGreaterEqual(res.data["total"], 2)

    def test_pagination_and_filters(self):
        self.auth_as(self.curator)

        # pagination
        res = self.client.get(self.url + "?page=1&pageSize=1")
        # pagination
        res = self.client.get(self.url + "?page=1&pageSize=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["page"], 1)
        self.assertEqual(res.data["pageSize"], 1)

        # search (OR across city/status/severity)
        res = self.client.get(self.url + "?search=Jakarta")
        # search (OR across city/status/severity)
        res = self.client.get(self.url + "?search=Jakarta")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any("Jakarta" in c["city"] for c in res.data["data"]))

        # exact filters
        res = self.client.get(self.url + "?gender=female&status=active&severity=high")
        # exact filters
        res = self.client.get(self.url + "?gender=female&status=active&severity=high")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(c["gender"] == "female" for c in res.data["data"]))

    def test_age_filter_and_sorting(self):
        self.auth_as(self.curator)
        res = self.client.get(self.url + "?minAge=20&maxAge=26&sort=age:desc")
        res = self.client.get(self.url + "?minAge=20&maxAge=26&sort=age:desc")
        self.assertEqual(res.status_code, 200)
        ages = [c["age"] for c in res.data["data"]]
        self.assertTrue(all(20 <= a <= 26 for a in ages))
        if len(ages) > 1:
            self.assertGreaterEqual(ages[0], ages[-1])

    def test_invalid_sort_fallback(self):
        self.auth_as(self.curator)
        res = self.client.get(self.url + "?sort=unknown:asc")
        res = self.client.get(self.url + "?sort=unknown:asc")
        self.assertEqual(res.status_code, 200)
        self.assertIn("data", res.data)

    def test_filter_by_location_and_disease(self):
        self.auth_as(self.curator)

        res = self.client.get(self.url + f"?location_id={self.case_a.location_id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            all(str(c["location_id"]) == str(self.case_a.location_id) for c in res.data["data"])
        )

        res = self.client.get(self.url + f"?disease_id={self.case_a.disease_id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            all(str(c["disease_id"]) == str(self.case_a.disease_id) for c in res.data["data"])
        )

    def test_min_only_max_only(self):
        self.auth_as(self.curator)

        res = self.client.get(self.url + "?minAge=26")

        res = self.client.get(self.url + "?minAge=26")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(c["age"] >= 26 for c in res.data["data"]))

        res = self.client.get(self.url + "?maxAge=26")
        res = self.client.get(self.url + "?maxAge=26")
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

        self.curator = DjangoUser.objects.create_user(
            username="curatora", password="pw", email="curatora@example.com"
        )
        setattr(self.curator, "role", "CURATOR")
        self.curator.save()

        self.curator.groups.add(self.grp_curator)

        self.other_user = DjangoUser.objects.create_user(
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
        self.user_role_only = DjangoUser.objects.create_user(
            username="roleonly@example.com", password="pw", email="roleonly@example.com"
        )
        setattr(self.user_role_only, "role", "CURATOR")
        self.user_role_only.save()

        self.user_group_only = DjangoUser.objects.create_user(
            username="grouponly@example.com", password="pw", email="grouponly@example.com"
        )
        self.user_group_only.groups.add(self.grp_curator)

        self.user_plain = DjangoUser.objects.create_user(
            username="plain@example.com", password="pw", email="plain@example.com"
        )

        # minimal data for GET OK - Fix duplicate id and attributes
        BackendCase.objects.create(
            id=uuid4(),
            gender="female",
            age=22, 
            city="Depok",
            status="active",
            disease_id=uuid4(),
            location_id=uuid4(),
            severity="low"
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

class ChartDataAPIViewTests(APITestCase):
    def setUp(self):
        self.url = "/api/logs/charts/data"
        self.user = PtUser.objects.create(
            name="Curator Uno",
            password="test-pass",
            role="CURATOR",
            email="curator@example.com",
        )
        token = RefreshToken.for_user(self.user).access_token
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        cache.clear()
        self._create_dataset()

    def test_requires_authentication(self):
        unauthenticated = APIClient()
        response = unauthenticated.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_chart_payload(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        charts = response.data.get("charts", {})
        self.assertIn("severityDistribution", charts)
        self.assertIn("meta", response.data)
        self.assertTrue(response.data["meta"].get("generatedAt"))
        severity_counts = {
            item["severity"]: item["count"]
            for item in charts["severityDistribution"]["data"]
        }
        self.assertGreaterEqual(severity_counts.get("hospitalisasi", 0), 1)
        self.assertGreaterEqual(severity_counts.get("insiden", 0), 1)
        self.assertEqual(charts["genderDistribution"]["chartType"], "pie")
        news_section = charts["newsCoverage"]["national"]
        self.assertEqual(news_section["top"][0]["portal"], "Portal Nasional")
        self.assertEqual(news_section["top"][0]["newsCount"], 1)
        trend_series = charts["severityTrendByDate"]["series"]
        self.assertTrue(any(series["points"] for series in trend_series))

    def test_filters_set_meta_flag(self):
        payload = {
            "diseases": ["Demam Berdarah"],
            "locations": {"provinces": ["Jawa Barat"]},
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["meta"]["filtersApplied"])

    @patch("curator_feature.views.ChartDataService.get_chart_data", side_effect=RuntimeError("boom"))
    def test_get_handles_service_error(self, mocked_service):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["message"], "Failed to fetch chart data")

    @patch("curator_feature.views.ChartDataService.get_chart_data", side_effect=RuntimeError("boom"))
    def test_post_handles_service_error(self, mocked_service):
        payload = {"diseases": ["Flu"]}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["message"], "Failed to fetch chart data")

    def test_serializer_to_filters_maps_all_fields(self):
        serializer = ChartDataFiltersSerializer(
            data={
                "diseases": ["Flu"],
                "portals": ["Portal"],
                "level_of_alertness": 3,
                "locations": {"provinces": ["Jawa Barat"], "cities": ["Bandung"]},
                "start_date": "2024-01-01",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        filters = serializer.to_filters()

        self.assertEqual(filters["disease"], ["Flu"])
        self.assertEqual(filters["portals"], ["Portal"])
        self.assertEqual(filters["disease_alertness"], 3)
        self.assertEqual(filters["provinces"], ["Jawa Barat"])
        self.assertEqual(filters["cities"], ["Bandung"])
        self.assertEqual(filters["date_range"]["start"], "2024-01-01")
        self.assertIsNone(filters["date_range"]["end"])

    def test_serializer_to_filters_handles_end_date_without_start(self):
        serializer = ChartDataFiltersSerializer(data={"end_date": "2024-01-10"})
        self.assertTrue(serializer.is_valid(), serializer.errors)

        filters = serializer.to_filters()

        self.assertEqual(filters["date_range"]["start"], None)
        self.assertEqual(filters["date_range"]["end"], "2024-01-10")

    def test_serializer_to_filters_skips_empty_date_range(self):
        serializer = ChartDataFiltersSerializer(data={})
        self.assertTrue(serializer.is_valid(), serializer.errors)

        filters = serializer.to_filters()

        self.assertNotIn("date_range", filters)

    def test_invalid_date_range_returns_400(self):
        payload = {"start_date": "2024-02-01", "end_date": "2024-01-01"}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)
        self.assertIn("end_date", response.data["errors"])

    def _create_dataset(self):
        disease_flu = Disease.objects.create(name="Flu", level_of_alertness=2)
        disease_dengue = Disease.objects.create(name="Demam Berdarah", level_of_alertness=3)

        loc_jakarta = Location.objects.create(
            latitude=Decimal("1.000000"),
            longitude=Decimal("120.000000"),
            city="Jakarta",
            province="DKI Jakarta",
        )
        loc_bandung = Location.objects.create(
            latitude=Decimal("2.000000"),
            longitude=Decimal("121.000000"),
            city="Bandung",
            province="Jawa Barat",
        )

        published_day_one = timezone.make_aware(datetime(2024, 1, 10, 10, 0))
        published_day_two = timezone.make_aware(datetime(2024, 1, 12, 10, 0))
        published_day_three = timezone.make_aware(datetime(2024, 1, 20, 10, 0))

        case_flu = Case.objects.create(
            gender="male",
            age=30,
            city="Jakarta",
            status="biasa",
            severity="hospitalisasi",
            disease=disease_flu,
            location=loc_jakarta,
        )
        case_dengue = Case.objects.create(
            gender="female",
            age=40,
            city="Bandung",
            status="bahaya",
            severity="insiden",
            disease=disease_dengue,
            location=loc_bandung,
        )
        case_mortal = Case.objects.create(
            gender="male",
            age=55,
            city="Jakarta",
            status="katastropik",
            severity="mortalitas",
            disease=disease_dengue,
            location=loc_jakarta,
        )

        News.objects.create(
            portal="Portal Nasional",
            title="National update",
            type="Nasional",
            content="National news content",
            url="https://example.com/national",
            author="Reporter 1",
            date_published=published_day_one,
            case=case_flu,
        )
        News.objects.create(
            portal="Portal Lokal",
            title="Local update",
            type="Lokal",
            content="Local news content",
            url="https://example.com/local",
            author="Reporter 2",
            date_published=published_day_two,
            case=case_dengue,
        )
        News.objects.create(
            portal="Portal Kesehatan",
            title="Healthcare update",
            type="Kesehatan",
            content="Healthcare news content",
            url="https://example.com/health",
            author="Reporter 3",
            date_published=published_day_three,
            case=case_mortal,
        )


class DownloadLogAPIViewTests(APITestCase):
    def setUp(self):
        self.url = "/api/logs/download"
        self.user = PtUser.objects.create(
            name="Curator Uno",
            password="test-pass",
            role="CURATOR",
            email="curator@example.com",
        )
        token = RefreshToken.for_user(self.user).access_token
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_requires_authentication(self):
        client = APIClient()
        payload = {
            "username": "Anon",
            "chartType": "BarChart",
            "timestamp": timezone.now().isoformat(),
        }
        response = client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logging_disabled_returns_accepted(self):
        payload = {
            "username": "KuratorA",
            "chartType": "BarChart",
            "timestamp": timezone.now().isoformat(),
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertFalse(response.data.get("logged", True))

    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_logs_download_event(self):
        payload = {
            "username": "KuratorA",
            "chartType": "BarChart",
            "timestamp": timezone.now().isoformat(),
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["username"], payload["username"])
        self.assertEqual(response.data["chartType"], payload["chartType"])
        self.assertTrue(DownloadLog.objects.filter(username="KuratorA").exists())

    def test_invalid_payload_returns_400(self):
        payload = {
            "username": "KuratorA",
            "timestamp": timezone.now().isoformat(),
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)
        self.assertIn("chartType", response.data["errors"])

    def test_blank_chart_type_returns_400(self):
        payload = {
            "username": "KuratorA",
            "chartType": "   ",
            "timestamp": timezone.now().isoformat(),
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("chartType", response.data.get("errors", {}))

    def test_invalid_timestamp_returns_400(self):
        payload = {
            "username": "KuratorA",
            "chartType": "LineChart",
            "timestamp": "not-a-date",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        errors = response.data.get("errors", {})
        self.assertIn("timestamp", errors)

    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_database_failure_returns_500(self):
        payload = {
            "username": "KuratorA",
            "chartType": "BarChart",
            "timestamp": timezone.now().isoformat(),
        }

        with patch("curator_feature.services.DownloadLogService.log_download", side_effect=DatabaseError("boom")):
            response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data.get("message"), "Download logging failed")


class DashboardDownloadEventAPIViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("dashboard-download-log")
        os.environ["SECRET_API_KEY"] = "test-api-key"
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY="test-api-key")

    def tearDown(self):
        os.environ.pop("SECRET_API_KEY", None)
        DashboardDownloadEvent.objects.all().delete()

    def _payload(self, **overrides):
        payload = {
            "metric": "jumlah_kasus",
            "file_format": "PNG",
            "filters": {"diseases": ["Dengue"]},
            "source": "dashboard",
        }
        payload.update(overrides)
        return payload

    def test_logging_disabled_returns_accepted(self):
        response = self.client.post(self.url, data=self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertFalse(response.data.get("logged", True))
        self.assertEqual(DashboardDownloadEvent.objects.count(), 0)

    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_logging_enabled_creates_event(self):
        response = self.client.post(self.url, data=self._payload(file_format="jpeg"), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data.get("logged"))
        self.assertEqual(DashboardDownloadEvent.objects.count(), 1)

        event = DashboardDownloadEvent.objects.get()
        self.assertEqual(event.metric, "jumlah_kasus")
        self.assertEqual(event.file_format, "jpeg")
        self.assertEqual(event.metadata["filters"]["diseases"], ["Dengue"])
        self.assertEqual(event.metadata["source"], "dashboard")


    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_logging_enabled_without_optional_metadata(self):
        payload = self._payload()
        payload.pop("filters")
        payload.pop("source")
        response = self.client.post(
            self.url,
            data=payload,
            format="json",
            HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = DashboardDownloadEvent.objects.get()
        self.assertIsNone(event.metadata)
        self.assertEqual(event.client_ip, "1.2.3.4")

    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_logging_uses_remote_addr_when_forward_headers_missing(self):
        payload = self._payload()
        payload.pop("filters")
        payload.pop("source")
        response = self.client.post(
            self.url,
            data=payload,
            format="json",
            REMOTE_ADDR="10.0.0.1",
            HTTP_USER_AGENT="",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = DashboardDownloadEvent.objects.get()
        self.assertEqual(event.client_ip, "10.0.0.1")
        self.assertEqual(event.user_agent, "")


class DashboardDownloadEventServiceTests(TestCase):
    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_log_event_re_raises_database_error(self):
        service = DashboardDownloadEventService()

        with patch(
            "curator_feature.services.DashboardDownloadEvent.objects.create",
            side_effect=DatabaseError("down"),
        ):
            with self.assertRaises(DatabaseError):
                service.log_event(
                    metric="jumlah_kasus",
                    file_format="png",
                    filters={"foo": "bar"},
                    source="dashboard",
                    client=ClientMetadata(ip_address="1.2.3.4", user_agent="agent"),
                )


class SerializerUnitTests(SimpleTestCase):
    def test_case_insensitive_choice_field_normalizes_strings(self):
        field = CaseInsensitiveChoiceField(choices=[("png", "PNG")])
        self.assertEqual(field.to_internal_value("PNG"), "png")

    def test_case_insensitive_choice_field_keeps_non_strings(self):
        field = CaseInsensitiveChoiceField(choices=[(1, "One")])
        self.assertEqual(field.to_internal_value(1), 1)

    def test_download_log_request_serializer_rejects_blank_fields(self):
        serializer = DownloadLogRequestSerializer(
            data={
                "username": "",
                "chartType": " ",
                "timestamp": timezone.now().isoformat(),
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("username", serializer.errors)
        self.assertIn("chartType", serializer.errors)

    def test_chart_data_filters_serializer_deduplicates_values(self):
        serializer = ChartDataFiltersSerializer(
            data={
                "diseases": ["Flu", "Flu"],
                "portals": ["A", "A"],
                "level_of_alertness": 2,
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
                "locations": {"provinces": ["Jawa Barat"], "cities": ["Bandung", "Bandung"]},
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["diseases"], ["Flu"])
        self.assertEqual(serializer.validated_data["portals"], ["A"])
        self.assertEqual(serializer.validated_data["locations"]["cities"], ["Bandung", "Bandung"])

    def test_chart_data_filters_to_filters_requires_validation(self):
        serializer = ChartDataFiltersSerializer()
        with self.assertRaises(AssertionError):
            serializer.to_filters()

    def test_dashboard_download_event_serializer_rejects_invalid_filters(self):
        serializer = DashboardDownloadEventSerializer(
            data={"metric": "jumlah_kasus", "file_format": "png", "filters": "oops"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("filters", serializer.errors)

    def test_dashboard_download_event_serializer_rejects_blank_source(self):
        serializer = DashboardDownloadEventSerializer(data={"metric": "jumlah_kasus", "file_format": "png", "source": ""})

        self.assertFalse(serializer.is_valid())
        self.assertIn("source", serializer.errors)

    def test_dashboard_download_event_serializer_normalizes_choices(self):
        serializer = DashboardDownloadEventSerializer(data={"metric": "JENIS_KELAMIN", "file_format": "JPEG"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["metric"], "jenis_kelamin")
        self.assertEqual(serializer.validated_data["file_format"], "jpeg")

    def test_download_log_request_field_validators_pass_through_values(self):
        serializer = DownloadLogRequestSerializer()
        self.assertEqual(serializer.validate_username("tester"), "tester")
        self.assertEqual(serializer.validate_chartType("line"), "line")

    def test_download_log_request_field_validators_raise_on_blank(self):
        serializer = DownloadLogRequestSerializer()
        with self.assertRaises(serializers.ValidationError):
            serializer.validate_username("")
        with self.assertRaises(serializers.ValidationError):
            serializer.validate_chartType("")

    def test_download_log_request_serializer_accepts_valid_payload(self):
        serializer = DownloadLogRequestSerializer(
            data={
                "username": "tester",
                "chartType": "line",
                "timestamp": timezone.now().isoformat(),
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["username"], "tester")
        self.assertEqual(serializer.validated_data["chartType"], "line")

    def test_dashboard_download_event_serializer_allows_valid_source(self):
        serializer = DashboardDownloadEventSerializer(
            data={
                "metric": "jumlah_kasus",
                "file_format": "png",
                "source": "dashboard",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["source"], "dashboard")
        self.assertIsNone(serializer.validate_filters(None))

    def test_dashboard_download_event_serializer_source_validator_raises_on_blank(self):
        serializer = DashboardDownloadEventSerializer()
        with self.assertRaises(serializers.ValidationError):
            serializer.validate_source("")


class DownloadLogResponseSerializerTests(TestCase):
    def test_download_log_response_serializer_maps_chart_type(self):
        entry = DownloadLog.objects.create(
            username="tester",
            chart_type="BarChart",
            timestamp=timezone.now(),
        )

        data = DownloadLogResponseSerializer(entry).data

        self.assertEqual(data["chartType"], "BarChart")
        self.assertEqual(data["username"], "tester")


class DownloadLogServiceTests(TestCase):
    def test_log_download_persists_entries(self):
        service = DownloadLogService()
        now = timezone.now()

        entry = service.log_download(username="tester", chart_type="pie", timestamp=now)

        self.assertEqual(entry.username, "tester")
        self.assertEqual(entry.chart_type, "pie")

    def test_log_download_wraps_database_errors(self):
        service = DownloadLogService()

        with patch("curator_feature.services.DownloadLog.objects.create", side_effect=DatabaseError("boom")):
            with self.assertRaises(DatabaseError):
                service.log_download(username="tester", chart_type="pie", timestamp=timezone.now())


class ChartDataServiceTests(SimpleTestCase):
    class StubCoordinator:
        def __init__(self, payload=None, exception=None):
            self.payload = payload
            self.exception = exception
            self.received_kwargs = None

        def generate_comprehensive_report(self, **kwargs):
            self.received_kwargs = kwargs
            if self.exception:
                raise self.exception
            return self.payload

    def _build_service(self, payload=None, exception=None):
        return ChartDataService(statistics_coordinator=self.StubCoordinator(payload=payload, exception=exception))

    def test_get_chart_data_returns_normalized_payload(self):
        payload = {
            "severity_statistics": {
                "severity_counts": {"hospitalisasi": "2", "insiden": 1, "custom": "3"},
                "total_cases": None,
            },
            "age_statistics": {"under_12": "1", "12_25": "2", "26_45": "3", "above_45": "4"},
            "gender_statistics": {"male": "5", "female": "6"},
            "severity_dates_count_statistics": {
                "hospitalisasi": [{"date": "2024-01-01", "count": "1"}, {"count": 5}],
                "unknown": "skip",
            },
            "prevalence_statistics": {
                "year": 2024,
                "total_cases": "10",
                "population": None,
                "prevalence": 0.5,
            },
            "national_news_statistics": {
                "top_national": [
                    {"portal": "Portal A", "count": "2"},
                    {"portal": None, "count": "3"},
                ],
                "all_national": [
                    {"portal": "Portal A", "news_count": "2", "disease_count": "1"},
                    {"portal": "Portal B", "count": "3", "disease_count": "2"},
                ],
            },
            "local_portal_statistics": {"error": "timeout"},
            "healthcare_news_statistics": None,
        }

        service = self._build_service(payload=payload)
        result = service.get_chart_data(filters={"disease": ["flu"]})

        self.assertTrue(result["meta"]["filtersApplied"])
        charts = result["charts"]
        self.assertEqual(charts["severityDistribution"]["meta"]["totalCases"], 6)
        self.assertEqual(charts["ageDistribution"]["meta"]["totalResponses"], 10)
        self.assertEqual(charts["genderDistribution"]["meta"]["totalCases"], 11)
        self.assertEqual(charts["severityTrendByDate"]["meta"]["seriesCount"], 1)
        self.assertEqual(charts["prevalence"]["data"]["totalCases"], 10)
        self.assertEqual(charts["prevalence"]["data"]["population"], None)
        self.assertEqual(charts["newsCoverage"]["national"]["meta"]["uniquePortals"], 2)
        self.assertEqual(charts["newsCoverage"]["local"]["meta"]["error"], "timeout")
        self.assertEqual(charts["newsCoverage"]["healthcare"]["meta"]["error"], "DATA_UNAVAILABLE")

    def test_get_chart_data_propagates_errors(self):
        service = self._build_service(exception=RuntimeError("failed"))

        with self.assertRaises(RuntimeError):
            service.get_chart_data(filters=None)

    def test_helper_methods_handle_edge_cases(self):
        service = self._build_service(payload={})

        severity_missing = service._format_severity(None)
        self.assertEqual(severity_missing["meta"]["error"], "DATA_UNAVAILABLE")
        severity_error = service._format_severity({"error": "down"})
        self.assertEqual(severity_error["meta"]["error"], "down")

        age_missing = service._format_age(None)
        self.assertEqual(age_missing["meta"]["error"], "DATA_UNAVAILABLE")
        age_error = service._format_age({"error": "down"})
        self.assertEqual(age_error["meta"]["error"], "down")

        gender_missing = service._format_gender(None)
        self.assertEqual(gender_missing["meta"]["error"], "DATA_UNAVAILABLE")
        gender_error = service._format_gender({"error": "down"})
        self.assertEqual(gender_error["meta"]["error"], "down")

        trend_missing = service._format_trend(None)
        self.assertEqual(trend_missing["meta"]["error"], "DATA_UNAVAILABLE")
        trend_error = service._format_trend({"error": "down"})
        self.assertEqual(trend_error["meta"]["error"], "down")

        prevalence_missing = service._format_prevalence(None)
        self.assertEqual(prevalence_missing["meta"]["error"], "DATA_UNAVAILABLE")
        prevalence_error = service._format_prevalence({"error": "down"})
        self.assertEqual(prevalence_error["meta"]["error"], "down")

        news_missing = service._normalize_news_section(None, "top", "all")
        self.assertEqual(news_missing["meta"]["error"], "DATA_UNAVAILABLE")
        news_error = service._normalize_news_section({"error": "down"}, "top", "all")
        self.assertEqual(news_error["meta"]["error"], "down")
        news_valid = service._normalize_news_section(
            {
                "top": [{"portal": "A", "count": "2"}],
                "all": [
                    {"portal": "A", "news_count": "2", "disease_count": "1"},
                    {"portal": "B", "count": "3", "disease_count": "2"},
                ],
            },
            "top",
            "all",
        )
        self.assertEqual(news_valid["meta"]["uniquePortals"], 2)

        trend_without_points = service._format_trend({"insiden": [{"count": 5}]})
        self.assertEqual(trend_without_points["meta"]["seriesCount"], 0)

        self.assertEqual(service._safe_int("5"), 5)
        self.assertEqual(service._safe_int("bad"), 0)
        self.assertIsNone(service._safe_int(None, allow_null=True))


class ModelRepresentationTests(TestCase):
    def test_download_log_str_returns_human_readable_form(self):
        entry = DownloadLog.objects.create(
            username="tester",
            chart_type="bar",
            timestamp=timezone.now(),
        )

        representation = str(entry)

        self.assertIn("tester", representation)
        self.assertIn("bar", representation)

    def test_dashboard_download_event_str_handles_missing_timestamp(self):
        event = DashboardDownloadEvent(metric="jumlah_kasus", file_format="png")
        self.assertIn("unknown", str(event))

    def test_dashboard_download_event_str_includes_timestamp(self):
        event = DashboardDownloadEvent.objects.create(metric="jumlah_kasus", file_format="png")
        self.assertIn("Jumlah Kasus", str(event))
        
import uuid
from datetime import datetime
from django.test import TestCase
from rest_framework.test import APIClient


CASES_BASE = "/curator-feature/curator/cases/"


class CuratorCaseAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # --- Users ---
        self.curator = PtUser.objects.create(
            id=123456,
            name="Curator One",
            email="curator@example.com",
            password="x",
        )
        setattr(self.curator, "role", "CURATOR")
        self.curator.save()

        self.other_user = PtUser.objects.create(
            id=789012,
            name="Viewer",
            email="viewer@example.com",
            password="x",
        )
        setattr(self.other_user, "role", "CONTRIBUTOR")
        self.other_user.save()

        # --- Seed master data ---
        self.disease_hb = Disease.objects.create(
            id=uuid.uuid4(), name="Hepatitis B", level_of_alertness=3
        )
        self.disease_dbd = Disease.objects.create(
            id=uuid.uuid4(), name="DBD", level_of_alertness=3
        )

        self.loc_palangka = Location.objects.create(
            id=uuid.uuid4(),
            city="Palangka Raya",
            province="Kalimantan Tengah",
            latitude=-2.156839,
            longitude=113.940011,
        )

        # Ambiguous city across provinces
        self.loc_sukabumi_jabar = Location.objects.create(
            id=uuid.uuid4(),
            city="Sukabumi",
            province="Jawa Barat",
            latitude=-6.906,
            longitude=106.928,
        )
        self.loc_sukabumi_dummy = Location.objects.create(
            id=uuid.uuid4(),
            city="Sukabumi",
            province="Jawa Barat (Kab.)",
            latitude=-6.934,
            longitude=106.925,
        )

    # ---------- helpers ----------
    def as_curator(self):
        self.client.force_authenticate(user=self.curator)

    def as_other(self):
        self.client.force_authenticate(user=self.other_user)

    def as_anon(self):
        # avoid logout signal issue by reinitializing client
        self.client = APIClient()

    # HAPPY PATH

    def test_create_case_with_existing_city_and_disease_name(self):
        """Create succeeds when disease and city exist; one News created."""
        self.as_curator()
        payload = {
            "disease": "Hepatitis B",
            "gender": "P",
            "age": 12,
            "city": "Palangka Raya",
            "status": "bahaya",
            "severity": "insiden",
            "location": {"city": "Palangka Raya"},
            "news": {
                "portal": "Kompas",
                "title": "Kasus Hepatitis Anak",
                "type": "artikel",
                "content": "Penyakit Hepatitis telah menyebar…",
                "url": "https://example.com/article",
                "author": "Reporter A",
                "date_published": "2024-01-23T00:00:00Z",
                "img_url": "",
            },
        }
        res = self.client.post(CASES_BASE, payload, format="json")
        self.assertEqual(res.status_code, 201, res.data)

        case = Case.objects.first()
        self.assertEqual(case.disease.name, "Hepatitis B")
        self.assertEqual(case.location.city, "Palangka Raya")
        self.assertEqual(case.status, "bahaya")
        self.assertEqual(case.severity, "insiden")
        self.assertEqual(News.objects.filter(case=case).count(), 1)

    def test_patch_update_disease_location_and_severity(self):
        """PATCH updates disease by name, resolves ambiguous city with provided province, and changes severity."""
        case = Case.objects.create(
            id=uuid.uuid4(),
            disease=self.disease_hb,
            location=self.loc_palangka,
            gender="P",
            age=12,
            city="Palangka Raya",
            status="biasa",
            severity="hospitalisasi",
        )
        self.as_curator()
        payload = {
            "disease": "DBD",
            "location": {"city": "Sukabumi", "province": "Jawa Barat"},
            "severity": "mortalitas",
        }
        res = self.client.patch(f"{CASES_BASE}{case.id}/", payload, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        case.refresh_from_db()
        self.assertEqual(case.disease.name, "DBD")
        self.assertEqual(case.location.city, "Sukabumi")
        self.assertEqual(case.severity, "mortalitas")

    def test_delete_case_and_cascade_news(self):
        """DELETE removes Case and cascades News (depends on FK on_delete)."""
        case = Case.objects.create(
            id=uuid.uuid4(),
            disease=self.disease_hb,
            location=self.loc_palangka,
            gender="P",
            age=12,
            city="Palangka Raya",
            status="bahaya",
            severity="insiden",
        )
        News.objects.create(
            case=case,
            portal="P",
            title="T",
            type="artikel",
            content="C",
            url="https://example.com/x",
            author="A",
            date_published=timezone.make_aware(datetime(2024, 1, 23)),
            img_url="",
        )

        self.as_curator()
        res = self.client.delete(f"{CASES_BASE}{case.id}/")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Case.objects.filter(id=case.id).exists())
        self.assertEqual(News.objects.filter(case_id=case.id).count(), 0)
    
    # NEGATIVE & EDGE CASES

    def test_patch_update_news_upserts_when_absent_and_updates_when_present(self):
        """PATCH first creates a News if none exists, then updates the latest on subsequent PATCH."""
        case = Case.objects.create(
            id=uuid.uuid4(),
            disease=self.disease_hb,
            location=self.loc_palangka,
            gender="P",
            age=12,
            city="Palangka Raya",
            status="biasa",
            severity="insiden",
        )
        self.as_curator()
        payload = {
            "news": {
                "portal": "Portal",
                "title": "T",
                "type": "artikel",
                "content": "C",
                "url": "https://example.com/x",
                "author": "A",
                "date_published": "2024-02-01T00:00:00Z",
                "img_url": "",
            }
        }
        # upsert create
        res = self.client.patch(f"{CASES_BASE}{case.id}/", payload, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(News.objects.filter(case=case).count(), 1)

        # update latest
        payload["news"]["title"] = "T2"
        res2 = self.client.patch(f"{CASES_BASE}{case.id}/", payload, format="json")
        self.assertEqual(res2.status_code, 200, res2.data)
        self.assertEqual(News.objects.get(case=case).title, "T2")

    def test_create_case_creates_new_location_when_not_found(self):
        """Create succeeds and auto-creates new Location when not found (with full fields)."""
        self.as_curator()
        payload = {
            "disease": "DBD",
            "gender": "L",
            "age": 10,
            "city": "Kota Baru",
            "status": "biasa",
            "severity": "mortalitas",
            "location": {
                "city": "Kota Baru",
                "province": "Kalimantan Selatan",
                "latitude": -3.442300,
                "longitude": 114.845500,
            },
            "news": {
                "portal": "Portal",
                "title": "Judul",
                "type": "artikel",
                "content": "Isi",
                "url": "https://example.com/x",
                "author": "Y",
                "date_published": "2024-02-01T00:00:00Z",
                "img_url": "",
            },
        }
        res = self.client.post(CASES_BASE, payload, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        case = Case.objects.get(id=res.data["id"])
        self.assertEqual(case.location.city, "Kota Baru")
        self.assertTrue(
            Location.objects.filter(
                city__iexact="Kota Baru", province__iexact="Kalimantan Selatan"
            ).exists()
        )

    def test_list_and_retrieve_include_read_fields(self):
        """List and Retrieve return expanded read fields (disease_name, location, news)."""
        case = Case.objects.create(
            id=uuid.uuid4(),
            disease=self.disease_hb,
            location=self.loc_palangka,
            gender="P",
            age=12,
            city="Palangka Raya",
            status="bahaya",
            severity="insiden",
        )
        News.objects.create(
            case=case,
            portal="Kompas",
            title="Kasus",
            type="artikel",
            content="x",
            url="https://example.com/x",
            author="y",
            date_published=timezone.make_aware(datetime(2024, 1, 23)),
            img_url="",
        )
        self.as_curator()
        res_list = self.client.get(CASES_BASE)
        self.assertEqual(res_list.status_code, 200)
        self.assertIn("disease_name", res_list.data[0])

        res_detail = self.client.get(f"{CASES_BASE}{case.id}/")
        self.assertEqual(res_detail.status_code, 200)
        self.assertEqual(res_detail.data["disease_name"], "Hepatitis B")
        self.assertEqual(len(res_detail.data["news"]), 1)

    def test_create_case_ambiguous_city_needs_province(self):
        """Ambiguous city w/o province -> 400 with helpful error."""
        self.as_curator()
        payload = {
            "disease": "DBD",
            "gender": "L",
            "age": 9,
            "city": "Sukabumi",
            "status": "minimal",
            "severity": "hospitalisasi",
            "location": {"city": "Sukabumi"},
            "news": {
                "portal": "Portal",
                "title": "A",
                "type": "artikel",
                "content": "B",
                "url": "https://example.com/valid",
                "author": "C",
                "date_published": "2024-01-23T00:00:00Z",
                "img_url": "",
            },
        }
        res = self.client.post(CASES_BASE, payload, format="json")
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn("location", res.data)

    def test_create_case_missing_fields_for_new_location(self):
        """Location not found and missing province/lat/lon -> 400 with missing fields listed."""
        self.as_curator()
        payload = {
            "disease": "DBD",
            "gender": "L",
            "age": 10,
            "city": "Kota Fiktif",
            "status": "katastropik",
            "severity": "insiden",
            "location": {"city": "Kota Fiktif"},
            "news": {
                "portal": "P",
                "title": "T",
                "type": "artikel",
                "content": "C",
                "url": "https://example.com/x",
                "author": "A",
                "date_published": "2024-02-01T00:00:00Z",
                "img_url": "",
            },
        }
        res = self.client.post(CASES_BASE, payload, format="json")
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn("location", res.data)

    def test_create_case_disease_name_not_found(self):
        """Disease name not found -> 400 with field error."""
        self.as_curator()
        payload = {
            "disease": "NotExist",
            "gender": "P",
            "age": 11,
            "city": "Palangka Raya",
            "status": "bahaya",
            "severity": "insiden",
            "location": {"city": "Palangka Raya"},
            "news": {
                "portal": "Portal",
                "title": "T",
                "type": "artikel",
                "content": "C",
                "url": "https://example.com/x",
                "author": "A",
                "date_published": "2024-02-01T00:00:00Z",
                "img_url": "",
            },
        }
        res = self.client.post(CASES_BASE, payload, format="json")
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn("disease", res.data)

    def test_create_case_invalid_status_or_severity(self):
        """Invalid status/severity enums -> 400 with field errors."""
        self.as_curator()
        payload = {
            "disease": "DBD",
            "gender": "L",
            "age": 10,
            "city": "Palangka Raya",
            "status": "wrongstatus",
            "severity": "wrongseverity",
            "location": {"city": "Palangka Raya"},
            "news": {
                "portal": "Portal",
                "title": "T",
                "type": "artikel",
                "content": "C",
                "url": "https://example.com/x",
                "author": "A",
                "date_published": "2024-02-01T00:00:00Z",
                "img_url": "",
            },
        }
        res = self.client.post(CASES_BASE, payload, format="json")
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn("status", res.data)
        self.assertIn("severity", res.data)

    def test_patch_ambiguous_city_requires_province(self):
        """PATCH with ambiguous city and no province -> 400."""
        case = Case.objects.create(
            id=uuid.uuid4(),
            disease=self.disease_hb,
            location=self.loc_palangka,
            gender="P",
            age=12,
            city="Palangka Raya",
            status="minimal",
            severity="insiden",
        )
        self.as_curator()
        res = self.client.patch(
            f"{CASES_BASE}{case.id}/",
            {"location": {"city": "Sukabumi"}},
            format="json",
        )
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn("location", res.data)

    def test_auth_required(self):
        """Anon access -> 401 on list."""
        self.as_anon()
        res = self.client.get(CASES_BASE)
        self.assertEqual(res.status_code, 401)

    def test_role_must_be_curator(self):
        """Non-curator role -> 403 on list."""
        self.as_other()
        res = self.client.get(CASES_BASE)
        self.assertEqual(res.status_code, 403)



class DashboardDownloadAPIKeyAuthExtraTests(APITestCase):
    def setUp(self):
        self.url = reverse("dashboard-download-log")

    def test_missing_api_key_denied(self):
        os.environ["SECRET_API_KEY"] = "super-secret"
        try:
            res = APIClient().post(self.url, data={}, format="json")
            self.assertIn(res.status_code, (401, 403))
        finally:
            os.environ.pop("SECRET_API_KEY", None)

    def test_wrong_api_key_denied(self):
        os.environ["SECRET_API_KEY"] = "super-secret"
        try:
            c = APIClient()
            c.credentials(HTTP_X_API_KEY="WRONG")
            res = c.post(self.url, data={}, format="json")
            self.assertIn(res.status_code, (401, 403))
        finally:
            os.environ.pop("SECRET_API_KEY", None)


class DashboardDownloadUserAgentTests(APITestCase):
    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_user_agent_and_xff_captured(self):
        os.environ["SECRET_API_KEY"] = "k"
        try:
            c = APIClient()
            c.credentials(HTTP_X_API_KEY="k")
            payload = {
                "metric": "jumlah_kasus",
                "file_format": "png",
                "filters": {"diseases": ["DBD"]},
                "source": "dashboard",
            }
            res = c.post(
                reverse("dashboard-download-log"),
                data=payload,
                format="json",
                HTTP_X_FORWARDED_FOR="8.8.8.8, 9.9.9.9",
                HTTP_USER_AGENT="pytest-agent",
            )
            self.assertEqual(res.status_code, 201, res.data)
            ev = DashboardDownloadEvent.objects.get()
            self.assertEqual(ev.client_ip, "8.8.8.8")      # first hop
            self.assertEqual(ev.user_agent, "pytest-agent")
        finally:
            os.environ.pop("SECRET_API_KEY", None)
            DashboardDownloadEvent.objects.all().delete()


class DownloadLogHTTPMethodTests(APITestCase):
    def setUp(self):
        self.url = "/api/logs/download"
        # auth user with JWT
        u = PtUser.objects.create(
            name="Curator X",
            email="cx@example.com",
            password="x",
            role="CURATOR",
        )
        token = RefreshToken.for_user(u).access_token
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_get_not_allowed(self):
        res = self.client.get(self.url)
        self.assertIn(res.status_code, (status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_404_NOT_FOUND))

    def test_put_not_allowed(self):
        res = self.client.put(self.url, data={}, format="json")
        self.assertIn(res.status_code, (status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_404_NOT_FOUND))


class CaseInsensitiveChoiceFieldErrorTests(SimpleTestCase):
    def test_invalid_choice_raises(self):
        field = CaseInsensitiveChoiceField(choices=[("png", "PNG"), ("jpeg", "JPEG")])
        with self.assertRaises(serializers.ValidationError):
            field.to_internal_value("gif")  # not in choices


class ChartDataFiltersSerializerDateValidationTests(SimpleTestCase):
    def test_end_before_start_is_invalid(self):
        s = ChartDataFiltersSerializer(
            data={"start_date": "2024-02-10", "end_date": "2024-02-01"}
        )
        self.assertFalse(s.is_valid())
        self.assertIn("end_date", s.errors)


class CuratorCasesSearchEmptyResults(APITestCase):
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
        # curator via Django Group
        grp, _ = Group.objects.get_or_create(name="CURATOR")
        self.curator = DjangoUser.objects.create_user(username="cur@example.com", password="x")
        self.curator.groups.add(grp)
        # seed a couple of rows
        BackendCase.objects.create(
            id=uuid4(), gender="female", age=25, city="Jakarta",
            status="active", disease_id=uuid4(), location_id=uuid4(), severity="high"
        )
        BackendCase.objects.create(
            id=uuid4(), gender="male", age=35, city="Bandung",
            status="recovered", disease_id=uuid4(), location_id=uuid4(), severity="low"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.curator)
        self.url = reverse("curator_cases_list")

    def test_search_no_match_returns_empty_list(self):
        res = self.client.get(self.url + "?search=NonexistentCity")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.get("data"), [])


class DashboardDownloadEventInvalidChoicesTests(APITestCase):
    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_invalid_metric_and_format_rejected(self):
        os.environ["SECRET_API_KEY"] = "k"
        try:
            c = APIClient()
            c.credentials(HTTP_X_API_KEY="k")
            res = c.post(
                reverse("dashboard-download-log"),
                data={"metric": "NOT_A_METRIC", "file_format": "NOT_A_FORMAT"},
                format="json",
            )
            self.assertEqual(res.status_code, 400)
            # both fields should be flagged by serializer
            self.assertTrue(
                "metric" in res.data or "errors" in res.data,
                msg=f"Unexpected response: {res.data}",
            )
        finally:
            os.environ.pop("SECRET_API_KEY", None)
            DashboardDownloadEvent.objects.all().delete()

    def test_is_curator_role_denies_anonymous(self):
        req = APIRequestFactory().get("/curator-feature/cases/")
        req.user = AnonymousUser()  # no auth
        perm = IsCuratorRole()
        assert perm.has_permission(req, None) is False

from django.db import connection
from django.db.utils import InternalError
from django.test import TestCase, override_settings
from curator_feature.models import CuratorDataLog
from django.utils import timezone
from uuid import uuid4

class CuratorDataLogImmutabilityTests(TestCase):
    def setUp(self):
        self.log = CuratorDataLog.objects.create(
            data_id=uuid4(),
            title="insiden",
            submitted_by="tester",
            note="seed",
            last_edited=timezone.now(),
        )

    def test_prevent_update_via_orm(self):
        self.log.note = "changed"
        with self.assertRaises(ValueError):
            self.log.save()

    def test_prevent_delete_via_orm(self):
        with self.assertRaises(ValueError):
            self.log.delete()

    def test_prevent_update_via_sql(self):
        with connection.cursor() as cur:
            with self.assertRaises(InternalError):
                cur.execute(
                    "UPDATE curator_feature_datalog SET note='sql' WHERE id=%s", [self.log.id]
                )

    def test_prevent_delete_via_sql(self):
        with connection.cursor() as cur:
            with self.assertRaises(InternalError):
                cur.execute(
                    "DELETE FROM curator_feature_datalog WHERE id=%s", [self.log.id]
                )


class CuratorDataLogSerializerHardeningTests(TestCase):
    def test_submitted_by_is_readonly(self):
        # client tries to forge submitted_by
        payload = {
            "data_id": str(uuid4()),
            "title": "insiden",
            "submitted_by": "evil",
        }
        from curator_feature.serializers import CuratorDataLogSerializer
        s = CuratorDataLogSerializer(data=payload)
        self.assertTrue(s.is_valid(), s.errors)
        # serializer should drop/ignore submitted_by (set by the view)
        self.assertNotIn("submitted_by", s.validated_data)


class CuratorDataLogHTTPMethodTests(APITestCase):
    def setUp(self):
        self.curator = PtUser.objects.create(
            name="Curator",
            email="c@example.com",
            password="x",
            role="CURATOR",
        )
        token = RefreshToken.for_user(self.curator).access_token
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.url = reverse("curator_audit_logs")

    def test_put_patch_delete_not_allowed(self):
        self.assertIn(self.client.put(self.url, data={}, format="json").status_code,
                      (status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_404_NOT_FOUND))
        self.assertIn(self.client.patch(self.url, data={}, format="json").status_code,
                      (status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_404_NOT_FOUND))
        self.assertIn(self.client.delete(self.url).status_code,
                      (status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_404_NOT_FOUND))
