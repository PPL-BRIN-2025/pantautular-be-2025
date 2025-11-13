import os

from curator_feature.admin import CuratorDataLogAdmin

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pantau_tular.test_settings")

import django
django.setup()
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Group, User as DjangoUser
from django.core.cache import cache
from django.db import DatabaseError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.test import APIClient, APIRequestFactory, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from curator_feature.models import CuratorDataLog, DashboardDownloadEvent, DownloadLog
from curator_feature.permissions import IsCuratorRole
from pt_backend.models import Case, Disease, Location, News, User as PtUser

from curator_feature.serializers import (
    CaseInsensitiveChoiceField,
    CaseReadSerializer,
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
        self.assertIn("locations", filters)
        self.assertEqual(filters["locations"]["provinces"], ["Jawa Barat"])
        self.assertEqual(filters["locations"]["cities"], ["Bandung"])
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
            date_published=datetime(2024, 1, 23, tzinfo=dt_timezone.utc),
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
        
from django.contrib import admin
from django.contrib.auth.models import User
        
class CuratorDataLogAdminTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_site = admin.site
        self.model_admin = CuratorDataLogAdmin(CuratorDataLog, self.admin_site)
        self.user = User.objects.create(username="tester")

    def test_list_and_readonly_fields_configured(self):
        self.assertIn("data_id", self.model_admin.list_display)
        self.assertIn("submitted_by", self.model_admin.list_filter)
        self.assertIn("note", self.model_admin.readonly_fields)
        self.assertIn("title", self.model_admin.search_fields)

    def test_has_change_and_delete_permission_always_false(self):
        request = self.factory.get("/")
        # ✅ Use valid UUID for data_id
        obj = CuratorDataLog.objects.create(
            data_id=uuid.uuid4(),
            title="Testing Log"
        )
        self.assertFalse(self.model_admin.has_change_permission(request))
        self.assertFalse(self.model_admin.has_delete_permission(request))
        self.assertFalse(self.model_admin.has_change_permission(request, obj))
        self.assertFalse(self.model_admin.has_delete_permission(request, obj))

import uuid
from django.test import TestCase
from curator_feature.models import CuratorDataLog


class CuratorDataLogModelCoverageTests(TestCase):
    def setUp(self):
        # Create an entry once for reuse
        self.entry = CuratorDataLog.objects.create(
            data_id=uuid.uuid4(),
            title="Outbreak Report",
            submitted_by="curator",
        )

    def test_str_representation_includes_all_fields(self):
        """Covers __str__ method (line 38)."""
        result = str(self.entry)
        self.assertIn("Outbreak Report", result)
        self.assertIn("curator", result)
        self.assertIn(str(self.entry.data_id), result)

    def test_save_raises_value_error_when_modifying_existing(self):
        """Covers immutability guard lines 42–43."""
        self.entry.title = "Edited"
        with self.assertRaises(ValueError) as context:
            self.entry.save()
        self.assertIn("immutable and cannot be modified", str(context.exception))

    def test_delete_raises_value_error(self):
        """Covers delete() immutability line 47."""
        with self.assertRaises(ValueError) as context:
            self.entry.delete()
        self.assertIn("cannot be deleted", str(context.exception))

from django.test import TestCase, RequestFactory
from curator_feature.permissions import IsCuratorRole, ReadOnlyOrCurator
from types import SimpleNamespace


class PermissionCoverageTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_is_curator_role_allows_curator(self):
        """Covers IsCuratorRole.has_permission for valid user role."""
        request = SimpleNamespace(user=SimpleNamespace(role="CURATOR"))
        perm = IsCuratorRole()
        self.assertTrue(perm.has_permission(request, None))

    def test_is_curator_role_denies_non_curator(self):
        """Covers IsCuratorRole.has_permission for invalid role."""
        request = SimpleNamespace(user=SimpleNamespace(role="viewer"))
        perm = IsCuratorRole()
        self.assertFalse(perm.has_permission(request, None))

    def test_readonly_or_curator_allows_safe_methods(self):
        """Covers lines 22–23: safe methods return True."""
        request = self.factory.get("/dummy")
        perm = ReadOnlyOrCurator()
        self.assertTrue(perm.has_permission(request, None))

    def test_readonly_or_curator_requires_token_and_curator_for_unsafe(self):
        """Covers lines 27–29: POST requires both token auth and curator role."""
        # Create fake request with method POST and valid role
        request = self.factory.post("/dummy")
        request.user = SimpleNamespace(role="CURATOR")
        # Patch IsTokenAuthenticated.has_permission to return True
        from authentication.permissions import IsTokenAuthenticated
        original_has_perm = IsTokenAuthenticated.has_permission
        IsTokenAuthenticated.has_permission = lambda self, req, view=None: True

        perm = ReadOnlyOrCurator()
        try:
            self.assertTrue(perm.has_permission(request, None))
        finally:
            # restore original behavior
            IsTokenAuthenticated.has_permission = original_has_perm

    def test_readonly_or_curator_denies_without_token_or_wrong_role(self):
        """Ensures unsafe method denied when not curator or no token."""
        request = self.factory.post("/dummy")
        request.user = SimpleNamespace(role="viewer")
        perm = ReadOnlyOrCurator()
        self.assertFalse(perm.has_permission(request, None))

import uuid
from django.test import TestCase
from django.utils import timezone
from curator_feature.models import CuratorDataLog
from curator_feature.services import log_curator_edit


class LogCuratorEditCoverageTests(TestCase):
    def test_log_curator_edit_creates_entry(self):
        """Covers line 389 in log_curator_edit()."""
        user = type("User", (), {"username": "curator_user", "email": "curator@example.com"})()
        data_id = uuid.uuid4()

        log_curator_edit(user=user, data_id=data_id, title="Health Report", note="Updated case data")

        entry = CuratorDataLog.objects.get(data_id=data_id)
        self.assertEqual(entry.title, "Health Report")
        self.assertEqual(entry.submitted_by, "curator_user")
        self.assertIsNotNone(entry.last_edited)
        self.assertEqual(entry.note, "Updated case data")

    def test_log_curator_edit_fallbacks_to_email_and_defaults(self):
        """Covers username/email fallback and title/note defaults."""
        user = type("User", (), {"email": "no_username@example.com"})()
        data_id = uuid.uuid4()

        log_curator_edit(user=user, data_id=data_id)  # no title/note provided

        entry = CuratorDataLog.objects.get(data_id=data_id)
        self.assertEqual(entry.title, "N/A")  # default title
        self.assertEqual(entry.submitted_by, "no_username@example.com")
        self.assertEqual(entry.note, "")
        self.assertLess(abs((entry.last_edited - timezone.now()).total_seconds()), 2)

from django.test import TestCase, RequestFactory
from curator_feature.views import DiseaseListCreateView


class DiseaseListCreateViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_get_permissions_safe_and_unsafe(self):
        """Covers get_permissions() for both branches."""
        view = DiseaseListCreateView()

        # Safe method: GET
        view.request = self.factory.get("/diseases")
        safe_perms = view.get_permissions()
        self.assertEqual(safe_perms, [])  # should allow everyone

        # Unsafe method: POST
        view.request = self.factory.post("/diseases")
        unsafe_perms = view.get_permissions()
        self.assertEqual(len(unsafe_perms), 1)
        self.assertEqual(unsafe_perms[0].__class__.__name__, "ReadOnlyOrCurator")

    def test_get_queryset_executes_lazy_import(self):
        """Covers lazy import lines 211–213."""
        view = DiseaseListCreateView()
        qs = view.get_queryset()
        self.assertTrue(hasattr(qs, "order_by"))
        # ensure ordering field is 'name'
        ordered = qs.query.order_by
        self.assertTrue("name" in str(ordered))

from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from curator_feature.views import CuratorCaseListCreateView


class CuratorCaseListCreateViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("curator_feature.views.log_curator_action", side_effect=Exception("logging failed"))
    @patch("curator_feature.views.logger")
    def test_perform_create_logs_exception(self, mock_logger, mock_log_action):
        """Covers exception handler in perform_create (lines 244–246)."""
        view = CuratorCaseListCreateView()
        view.request = self.factory.post("/curator/cases/")
        serializer = MagicMock()

        # Simulate instance with attributes used in logging
        instance = MagicMock(id="uuid123", severity=None, status=None)
        serializer.save.return_value = instance

        # Run perform_create (should hit except block)
        view.perform_create(serializer)

        # Verify logger.exception() was called once with correct message
        mock_logger.exception.assert_called_once()
        args, kwargs = mock_logger.exception.call_args
        self.assertIn("audit-log create failed", args[0])

from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from curator_feature.views import CuratorCaseDetailView


class CuratorCaseDetailViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("curator_feature.views.log_curator_action", side_effect=Exception("update failed"))
    @patch("curator_feature.views.logger")
    def test_perform_update_logs_exception(self, mock_logger, mock_log_action):
        """Covers lines 272–273: perform_update exception handler."""
        view = CuratorCaseDetailView()
        view.request = self.factory.patch("/curator/cases/uuid")
        serializer = MagicMock()

        instance = MagicMock(id="uuid123", severity=None, status=None)
        serializer.save.return_value = instance

        # Trigger perform_update() -> should hit except block
        view.perform_update(serializer)

        mock_logger.exception.assert_called_once()
        args, kwargs = mock_logger.exception.call_args
        self.assertIn("audit-log update failed", args[0])

    @patch("curator_feature.views.log_curator_action", side_effect=Exception("delete failed"))
    @patch("curator_feature.views.logger")
    def test_perform_destroy_logs_exception(self, mock_logger, mock_log_action):
        """Covers lines 284–285: perform_destroy exception handler."""
        view = CuratorCaseDetailView()
        view.request = self.factory.delete("/curator/cases/uuid")

        instance = MagicMock(id="uuid123", severity=None, status=None)

        # Trigger perform_destroy() -> should hit except block
        view.perform_destroy(instance)

        mock_logger.exception.assert_called_once()
        args, kwargs = mock_logger.exception.call_args
        self.assertIn("audit-log delete failed", args[0])

from django.test import TestCase
from curator_feature.views import CuratorDiseaseListCreateView


class CuratorDiseaseListCreateViewTests(TestCase):
    def test_get_queryset_lazy_import_executes(self):
        """Covers lines 301–303 in get_queryset()."""
        view = CuratorDiseaseListCreateView()
        qs = view.get_queryset()

        # Verify it's a Django queryset and ordered by 'name'
        self.assertTrue(hasattr(qs, "order_by"))
        ordering = qs.query.order_by
        self.assertTrue("name" in str(ordering))

import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from rest_framework import status
from curator_feature.views import CuratorDataLogListCreateAPIView


class CuratorDataLogListCreateAPIViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        # Patch out permissions/auth so the view runs freely
        patcher1 = patch.object(CuratorDataLogListCreateAPIView, "authentication_classes", [])
        patcher2 = patch.object(CuratorDataLogListCreateAPIView, "permission_classes", [])
        patcher1.start()
        patcher2.start()
        self.addCleanup(patcher1.stop)
        self.addCleanup(patcher2.stop)

    @patch("curator_feature.views.CuratorDataLogSerializer")
    @patch("curator_feature.views.CuratorDataLog.objects")
    def test_get_with_all_filters_and_sorting(self, mock_mgr, mock_serializer):
        """Covers all branches in GET: _i, filters, sorting, pagination, Response."""
        mock_qs = MagicMock()
        mock_mgr.all.return_value = mock_qs
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 5
        mock_qs.order_by.return_value = [MagicMock()]
        mock_serializer.return_value.data = [{"id": "x"}]

        request = self.factory.get(
            "/logs",
            {
                "page": "1",
                "pageSize": "10",
                "search": "covid",
                "submitted_by": "curator",
                "start": "2024-01-01",
                "end": "2024-12-31",
                "sort": "title:asc",
            },
        )
        request.user = MagicMock(role="CURATOR")
        response = CuratorDataLogListCreateAPIView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("curator_feature.views.CuratorDataLogSerializer")
    @patch("curator_feature.views.CuratorDataLog.objects")
    def test_get_with_invalid_int_and_defaults(self, mock_mgr, mock_serializer):
        """Covers _i() exception path (non-int values)."""
        mock_qs = MagicMock()
        mock_mgr.all.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_qs.order_by.return_value = []
        mock_serializer.return_value.data = []

        request = self.factory.get("/logs", {"page": "bad", "pageSize": "oops"})
        request.user = MagicMock(role="CURATOR")
        response = CuratorDataLogListCreateAPIView.as_view()(request)
        self.assertEqual(response.status_code, 200)

    @patch("curator_feature.views.CuratorDataLogSerializer")
    @patch("curator_feature.views.BackendCase")
    def test_post_success_and_invalid(self, mock_case_cls, mock_serializer_cls):
        """Covers POST success (201) and invalid serializer (400)."""
        # ensure BackendCase.objects.get doesn't crash
        mock_case_cls.objects.get.side_effect = mock_case_cls.DoesNotExist
        mock_case_cls.DoesNotExist = Exception  # dummy attr to satisfy except

        mock_valid_ser = MagicMock()
        mock_valid_ser.is_valid.return_value = True
        mock_valid_ser.data = {"ok": True}
        mock_serializer_cls.return_value = mock_valid_ser

        # Valid request
        request = self.factory.post("/logs", {"data_id": str(uuid.uuid4()), "title": "test"})
        request.user = MagicMock(username="curator", email="curator@example.com", role="CURATOR")
        response = CuratorDataLogListCreateAPIView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Invalid serializer (400)
        mock_invalid_ser = MagicMock()
        mock_invalid_ser.is_valid.return_value = False
        mock_invalid_ser.errors = {"error": "bad"}
        mock_serializer_cls.return_value = mock_invalid_ser
        request = self.factory.post("/logs", {"data_id": str(uuid.uuid4())})
        request.user = MagicMock(username="", email="curator@example.com", role="CURATOR")
        response = CuratorDataLogListCreateAPIView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("curator_feature.views.CuratorDataLogSerializer")
    @patch("curator_feature.views.BackendCase")
    def test_post_missing_title_and_does_not_exist(self, mock_case_cls, mock_serializer_cls):
        """Covers BackendCase.DoesNotExist and missing title branch."""
        mock_case_cls.DoesNotExist = Exception  # add attribute to mock class
        mock_case_cls.objects.get.side_effect = mock_case_cls.DoesNotExist  # trigger except

        mock_serializer = MagicMock()
        mock_serializer.is_valid.return_value = True
        mock_serializer.data = {"created": True}
        mock_serializer_cls.return_value = mock_serializer

        request = self.factory.post("/logs", {"data_id": str(uuid.uuid4())})
        request.user = MagicMock(username="", email="backup@example.com", role="CURATOR")

        response = CuratorDataLogListCreateAPIView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_case_cls.objects.get.assert_called_once()


class CaseReadSerializerTests(SimpleTestCase):
    def test_get_batch_returns_payload(self):
        batch = SimpleNamespace(
            id=uuid4(),
            filename="cases.csv",
            uploaded_at=timezone.now(),
        )
        serializer = CaseReadSerializer()
        result = serializer.get_batch(SimpleNamespace(batch=batch))
        self.assertEqual(result["filename"], "cases.csv")
        self.assertEqual(result["id"], str(batch.id))

    def test_get_batch_handles_missing_batch(self):
        serializer = CaseReadSerializer()
        self.assertIsNone(serializer.get_batch(SimpleNamespace(batch=None)))
