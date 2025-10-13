import os
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

from pt_backend.models import Case, Disease, Location, News, User
from curator_feature.models import DownloadLog, DashboardDownloadEvent
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


class ChartDataAPIViewTests(APITestCase):
    def setUp(self):
        self.url = "/api/logs/charts/data"
        self.user = User.objects.create(
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
        self.user = User.objects.create(
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
from datetime import datetime, timezone
from django.test import TestCase
from rest_framework.test import APIClient
from pt_backend.models import Case, Disease, Location, News, User


CASES_BASE = "/curator-feature/curator/cases/"


class CuratorCaseAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # --- Users ---
        self.curator = User.objects.create(
            id=123456,
            name="Curator One",
            email="curator@example.com",
            password="x",
        )
        setattr(self.curator, "role", "CURATOR")
        self.curator.save()

        self.other_user = User.objects.create(
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
                date_published=datetime(2024, 1, 23, tzinfo=timezone.utc),
                img_url="",
            )

            self.as_curator()
            res = self.client.delete(f"{CASES_BASE}{case.id}/")
            self.assertEqual(res.status_code, 204)
            self.assertFalse(Case.objects.filter(id=case.id).exists())
            self.assertEqual(News.objects.filter(case_id=case.id).count(), 0)

