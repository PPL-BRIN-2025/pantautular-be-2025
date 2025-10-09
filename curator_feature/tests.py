import os
from django.utils import timezone
from django.db import DatabaseError
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch
from django.test import override_settings
from django.urls import reverse

from pt_backend.models import User
from curator_feature.models import DownloadLog, DashboardDownloadEvent


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
