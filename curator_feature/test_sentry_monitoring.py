from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.test import TestCase, RequestFactory
from rest_framework.test import APIClient
from rest_framework import status

from pt_backend.models import User as PtUser
from rest_framework_simplejwt.tokens import RefreshToken


class TestSentryMonitoring(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.factory = RequestFactory()

        # Create curator user
        self.user = PtUser.objects.create(
            name="Curator",
            email="curator@test.com",
            password="password123",
            role="CURATOR",
        )

        # Create JWT token
        self.token = str(RefreshToken.for_user(self.user).access_token)

        self.auth_header = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    # ------------------------------------------------------------------
    # 1) Test List Case Sentry Monitoring
    # ------------------------------------------------------------------
    @patch("curator_feature.views.log_event")
    @patch("curator_feature.views.record_duration")
    def test_sentry_case_list(self, mock_duration, mock_log_event):
        mock_duration.return_value = MagicMock()

        # CORRECT URL name
        url = reverse("curator-cases")

        response = self.client.get(url, **self.auth_header)

        # Response should NOT break
        self.assertIn(response.status_code, [200, 204])

        # record_duration must be called
        self.assertGreaterEqual(mock_duration.call_count, 1)

        # Validate sentry events logged
        event_names = [call.args[0] for call in mock_log_event.call_args_list]
        self.assertIn("curator.case.list.success", event_names)

    # ------------------------------------------------------------------
    # 2) Test Create Case Sentry Monitoring
    # ------------------------------------------------------------------
    @patch("curator_feature.views.log_event")
    @patch("curator_feature.views.record_duration")
    def test_sentry_case_create(self, mock_duration, mock_log_event):
        mock_duration.return_value = MagicMock()

        # CORRECT URL name
        url = reverse("curator-cases")

        payload = {
            "disease": 1,
            "location": 1,
            "severity": "High",
            "status": "Confirmed",
            "notes": "Test creation",
        }

        response = self.client.post(url, payload, format="json", **self.auth_header)

        # Any valid or invalid payload shouldn't break monitoring
        self.assertIn(response.status_code, [201, 200, 400])

        # duration wrapper should be called
        self.assertGreaterEqual(mock_duration.call_count, 1)

        # Should log success OR invalid
        event_names = [call.args[0] for call in mock_log_event.call_args_list]
        self.assertTrue(any("curator.case.create" in name for name in event_names))

    # ------------------------------------------------------------------
    # 3) Test _monitoring_context values
    # ------------------------------------------------------------------
    def test_monitoring_context_structure(self):
        from curator_feature.views import _monitoring_context

        request = self.factory.get("/dummy")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "123.55.11.20"

        ctx = _monitoring_context(request, "test_endpoint", extra_key="XYZ")

        self.assertEqual(ctx["endpoint"], "test_endpoint")
        self.assertEqual(ctx["user_id"], self.user.id)
        self.assertEqual(ctx["client_ip"], "123.55.11.20")
        self.assertEqual(ctx["extra_key"], "XYZ")

    # ------------------------------------------------------------------
    # 4) Test Chart GET Monitoring
    # ------------------------------------------------------------------
    @patch("curator_feature.views.log_event")
    @patch("curator_feature.views.record_duration")
    def test_sentry_chart_get(self, mock_duration, mock_log_event):
        mock_duration.return_value = MagicMock()

        # CORRECT URL name
        url = reverse("curator-charts-data")

        response = self.client.get(url, **self.auth_header)

        self.assertIn(response.status_code, [200, 204])

        # duration wrapper called
        self.assertGreaterEqual(mock_duration.call_count, 1)

        # logs must contain chart fetch success event
        event_names = [call.args[0] for call in mock_log_event.call_args_list]
        self.assertIn("curator.chart.fetch.success", event_names)
