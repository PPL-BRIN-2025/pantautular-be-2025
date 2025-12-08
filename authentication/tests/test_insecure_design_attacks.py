from uuid import uuid4

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from curator_feature.models import ContributorSubmission
from pantau_tular.security import AntiAutomationRules, BusinessLogicGuard
from pt_backend.models import User


class SecureDesignAttackTests(TestCase):
    """Attack simulations covering OWASP A06:2025 insecure design scenarios."""

    def setUp(self):
        self.curator = User.objects.create(
            name="Curator",
            email="curator@example.com",
            password="p@ssw0rd",
            role="CURATOR",
        )
        self.auth_client = APIClient()
        self.auth_client.force_authenticate(user=self.curator)
        self.api_client = APIClient()
        self.api_headers = {
            "HTTP_X_API_KEY": next(iter(settings.SECRET_API_KEYS), "test-api-key"),
            "HTTP_X_CLIENT_ID": "chart-client",
        }
        BusinessLogicGuard._GLOBAL_DOWNLOAD_EVENTS.clear()
        AntiAutomationRules._GLOBAL_EVENTS.clear()
        self.status_url = lambda submission_id: reverse(
            "curator-submission-status",
            args=[submission_id],
        )
        self.download_url = reverse("curator-dashboard-download-log")

    def _create_submission(self, *, status_value="WAITING_FOR_APPROVAL", submitted_by="tenant-alpha::alice@example.com"):
        submission = ContributorSubmission.objects.create(
            id=uuid4(),
            title="Case Study",
            content="payload",
            submitted_by=submitted_by,
            status=status_value,
        )
        return submission

    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_business_logic_abuse_rate_limited_chart_exports(self):
        """Attack Scenario B — repeated chart export attempts trip BusinessLogicGuard."""
        payload = {
            "metric": "jumlah_kasus",
            "file_format": "png",
            "source": "dashboard-tests",
        }
        for _ in range(BusinessLogicGuard.CHART_DOWNLOAD_LIMIT):
            resp = self.api_client.post(self.download_url, payload, format="json", **self.api_headers)
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        abusive = self.api_client.post(self.download_url, payload, format="json", **self.api_headers)
        self.assertEqual(abusive.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("limit", abusive.data["detail"].lower())

    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_anti_automation_blocks_bot_like_downloads(self):
        """Attack Scenario C — AntiAutomationRules blocks high-speed downloads."""
        original_limit = BusinessLogicGuard.CHART_DOWNLOAD_LIMIT
        BusinessLogicGuard.CHART_DOWNLOAD_LIMIT = 10  # prevent business guard from firing first
        self.addCleanup(lambda: setattr(BusinessLogicGuard, "CHART_DOWNLOAD_LIMIT", original_limit))

        payload = {
            "metric": "jumlah_kasus",
            "file_format": "png",
            "source": "bot-runner",
        }
        for _ in range(5):
            resp = self.api_client.post(self.download_url, payload, format="json", **self.api_headers)
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        burst = self.api_client.post(self.download_url, payload, format="json", **self.api_headers)
        self.assertEqual(burst.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("anti-automation", burst.data["detail"].lower())

    def test_workflow_validator_blocks_unreviewed_approval(self):
        """Attack Scenario A — workflow transitions require review notes."""
        submission = self._create_submission()
        resp = self.auth_client.patch(
            self.status_url(submission.id),
            {"status": "APPROVED"},
            format="json",
            HTTP_X_TENANT_ID="tenant-alpha",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("requires", resp.data["detail"])

    def test_tier_boundary_rejects_internal_field_forging(self):
        """Attack Scenario D — TierBoundaryEnforcer rejects internal-only fields."""
        submission = self._create_submission()
        resp = self.auth_client.patch(
            self.status_url(submission.id),
            {"status": "NEED_REVISION", "has_unseen_update": False},
            format="json",
            HTTP_X_TENANT_ID="tenant-alpha",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("internal fields", resp.data["detail"])

    def test_tenant_segregation_blocks_cross_tenant_access(self):
        """Attack Scenario E — tenant-aware guard prevents cross-tenant updates."""
        submission = self._create_submission(submitted_by="tenant-bravo::bob@example.com")
        resp = self.auth_client.patch(
            self.status_url(submission.id),
            {"status": "NEED_REVISION", "note": "Requires changes"},
            format="json",
            HTTP_X_TENANT_ID="tenant-alpha",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("tenant", resp.data["detail"].lower())
