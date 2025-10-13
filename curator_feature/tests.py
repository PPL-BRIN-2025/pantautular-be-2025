import os
from datetime import datetime
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone
from django.db import DatabaseError
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch
from django.test import override_settings
from django.urls import reverse

from pt_backend.models import Case, Disease, Location, News, User
from curator_feature.models import DownloadLog, DashboardDownloadEvent


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
