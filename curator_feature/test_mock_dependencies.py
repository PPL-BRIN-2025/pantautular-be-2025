import os
from types import SimpleNamespace
from uuid import uuid4

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pantau_tular.test_settings")

import django

django.setup()

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    ValidationError as DRFValidationError,
    PermissionDenied as DRFPermissionDenied,
)
from rest_framework.test import APIRequestFactory

from curator_feature.models import ContributorSubmission, DownloadLog
from curator_feature.services import ChartDataService, ContributorSubmissionService
from curator_feature.views import (
    ChartsSimpleView,
    ChartDataAPIView,
    DownloadLogAPIView,
    DashboardDownloadEventAPIView,
    CuratorCaseListCreateView,
    CuratorCaseDetailView,
    ContributorSubmissionListView,
    ContributorSubmissionStatusUpdateView,
    ContributorSubmissionMarkSeenView,
)


class ChartsSimpleViewMockTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("curator_feature.views.ChartDataService.get_chart_data", return_value={"charts": {"foo": "bar"}})
    def test_get_returns_payload_when_service_succeeds(self, mock_service):
        response = ChartsSimpleView.as_view()(self.factory.get("/charts/simple"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["charts"]["foo"], "bar")
        mock_service.assert_called_once()



class DownloadLogAPIViewMockTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.payload = {
            "username": "Tester",
            "chartType": "BarChart",
            "timestamp": timezone.now().isoformat(),
        }

    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    @patch.object(DownloadLogAPIView, "authentication_classes", new=[])
    @patch.object(DownloadLogAPIView, "permission_classes", new=[])
    @patch("curator_feature.views.DownloadLogService.log_download")
    def test_post_uses_service_and_serializer(self, mock_log_download):
        entry = DownloadLog(username="Tester", chart_type="BarChart", timestamp=timezone.now())
        entry.id = 99
        entry.created_at = timezone.now()
        mock_log_download.return_value = entry

        response = DownloadLogAPIView.as_view()(self.factory.post("/download", self.payload, format="json"))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["username"], "Tester")
        mock_log_download.assert_called_once()




class ContributorSubmissionMarkSeenViewMockTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch.object(ContributorSubmissionMarkSeenView, "authentication_classes", new=[])
    @patch.object(ContributorSubmissionMarkSeenView, "permission_classes", new=[])
    @patch("curator_feature.views.ContributorSubmission.objects.get")
    def test_mark_seen_resets_flag(self, mock_get):
        submission = SimpleNamespace(id=uuid4(), has_unseen_update=True)
        submission.save = MagicMock()
        mock_get.return_value = submission

        request = self.factory.patch("/mark-seen", format="json")
        request.user = SimpleNamespace(role="CURATOR")
        response = ContributorSubmissionMarkSeenView.as_view()(request, id=submission.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(submission.has_unseen_update)
        submission.save.assert_called_once_with(update_fields=["has_unseen_update"])
