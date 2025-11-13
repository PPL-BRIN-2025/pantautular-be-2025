import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pantau_tular.test_settings")

import uuid

import django

django.setup()

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.test import APIClient, APIRequestFactory

from curator_feature.models import DashboardDownloadEvent
from expert_user_feature.permissions import IsExpertUserRole, ReadOnlyOrExpert
from expert_user_feature.serializers import CaseReadSerializer, CaseWriteSerializer, ExpertDashboardDownloadSerializer
from expert_user_feature.views import ExpertCaseCreateView, ExpertDashboardCSVDownloadAPIView
from pt_backend.models import Case, Disease, Location, News, User as PtUser


LOG_URL = "/expert-feature/downloads/log/"
CSV_URL = "/expert-feature/downloads/csv/"


class ExpertDownloadAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = PtUser.objects.create(
            name="Expert",
            email="expert@example.com",
            password="pwd",
            role="EXP_USER",
        )
        self.client.force_authenticate(user=self.user)

        self.disease_high = Disease.objects.create(name="DBD", level_of_alertness=3)
        self.disease_low = Disease.objects.create(name="Flu", level_of_alertness=1)

        self.location_jakarta = Location.objects.create(city="Jakarta", province="DKI Jakarta")
        self.location_bandung = Location.objects.create(city="Bandung", province="Jawa Barat")

        self.case_with_news = Case.objects.create(
            disease=self.disease_high,
            location=self.location_jakarta,
            gender="P",
            age=30,
            city="Jakarta",
            status="bahaya",
            severity="insiden",
        )
        self.news_article = News.objects.create(
            case=self.case_with_news,
            portal="Portal A",
            title="Berita Kasus",
            type="artikel",
            content="Isi berita",
            url="https://example.com/a",
            author="Reporter A",
            date_published=timezone.make_aware(datetime(2024, 3, 10, 8, 0, 0)),
            img_url="https://example.com/a.png",
        )

        self.case_no_news = Case.objects.create(
            disease=self.disease_high,
            location=self.location_jakarta,
            gender="L",
            age=45,
            city="Jakarta",
            status="biasa",
            severity="hospitalisasi",
        )

        self.case_filtered_out = Case.objects.create(
            disease=self.disease_low,
            location=self.location_bandung,
            gender="L",
            age=19,
            city="Bandung",
            status="minimal",
            severity="hospitalisasi",
        )
        News.objects.create(
            case=self.case_filtered_out,
            portal="Portal Z",
            title="Berita Lain",
            type="artikel",
            content="Berita luar filter",
            url="https://example.com/z",
            author="Reporter Z",
            date_published=timezone.make_aware(datetime(2023, 1, 5, 12, 0, 0)),
            img_url="https://example.com/z.png",
        )

    def tearDown(self):
        DashboardDownloadEvent.objects.all().delete()

    def _filters_payload(self):
        start = (self.news_article.date_published - timedelta(days=1)).date().isoformat()
        end = (self.news_article.date_published + timedelta(days=1)).date().isoformat()
        return {
            "diseases": [self.disease_high.name],
            "portals": ["Portal A"],
            "level_of_alertness": self.disease_high.level_of_alertness,
            "locations": {
                "cities": [self.location_jakarta.city],
                "provinces": [self.location_jakarta.province],
            },
            "start_date": start,
            "end_date": end,
        }

    def test_download_log_returns_accepted_when_logging_disabled(self):
        payload = {
            "metric": "jumlah_kasus",
            "file_format": "png",
            "source": "expert-dashboard",
        }

        response = self.client.post(LOG_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertFalse(response.data["logged"])
        self.assertEqual(DashboardDownloadEvent.objects.count(), 0)

    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_download_log_creates_event_when_enabled(self):
        payload = {
            "metric": "jumlah_kasus",
            "file_format": "png",
            "filters": self._filters_payload(),
            "source": "expert-dashboard",
        }

        response = self.client.post(LOG_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(response.data["logged"])
        event = DashboardDownloadEvent.objects.get()
        self.assertEqual(event.metric, "jumlah_kasus")
        self.assertEqual(event.file_format, "png")
        self.assertEqual(event.metadata["filters"]["diseases"], [self.disease_high.name])
        self.assertEqual(event.metadata["source"], "expert-dashboard")

    def test_download_log_returns_validation_errors(self):
        response = self.client.post(LOG_URL, {"file_format": "png"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_download_log_handles_persistence_failure(self):
        payload = {
            "metric": "jumlah_kasus",
            "file_format": "png",
            "source": "expert-dashboard",
        }

        with patch("expert_user_feature.views.DashboardDownloadEventService.log_event", side_effect=Exception("db failure")):
            response = self.client.post(LOG_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["message"], "Download logging failed")

    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_csv_download_returns_file_and_logs_event(self):
        payload = {
            "metric": "jumlah_kasus",
            "file_format": "csv",
            "filters": self._filters_payload(),
            "source": "expert-dashboard",
        }

        response = self.client.post(CSV_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertEqual(response["X-Download-Logged"], "true")
        self.assertIn('attachment; filename="jumlah_kasus-export.csv"', response["Content-Disposition"])
        csv_rows = response.content.decode("utf-8").splitlines()
        self.assertEqual(len(csv_rows), 2)
        data_row = csv_rows[1].split(",")
        self.assertEqual(data_row[0], str(self.case_with_news.id))
        self.assertEqual(data_row[9], "Portal A")
        self.assertEqual(DashboardDownloadEvent.objects.count(), 1)

    def test_csv_download_includes_blank_news_columns(self):
        payload = {
            "metric": "jumlah_kasus",
            "filters": {
                "diseases": [self.disease_high.name],
                "locations": {"cities": [self.location_jakarta.city]},
            },
        }

        response = self.client.post(CSV_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        csv_rows = response.content.decode("utf-8").splitlines()
        no_news_row = next(row for row in csv_rows[1:] if row.startswith(str(self.case_no_news.id)))
        columns = no_news_row.split(",")
        self.assertTrue(all(value == "" for value in columns[9:]))
        self.assertEqual(response["X-Download-Logged"], "false")

    def test_csv_download_filters_outside_requests(self):
        payload = {
            "metric": "jumlah_kasus",
            "file_format": "csv",
            "filters": self._filters_payload(),
        }

        response = self.client.post(CSV_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        csv_rows = response.content.decode("utf-8").splitlines()
        ids_returned = {row.split(",")[0] for row in csv_rows[1:]}
        self.assertIn(str(self.case_with_news.id), ids_returned)
        self.assertNotIn(str(self.case_filtered_out.id), ids_returned)

    def test_filtered_cases_handles_location_filters(self):
        view = ExpertDashboardCSVDownloadAPIView()
        filters = {
            "diseases": [self.disease_high.name],
            "locations": {
                "provinces": [self.location_jakarta.province],
                "cities": [self.location_jakarta.city],
            },
        }
        qs = view._filtered_cases(filters)
        self.assertIn(self.case_with_news, qs)

    def test_filtered_cases_without_province(self):
        view = ExpertDashboardCSVDownloadAPIView()
        filters = {
            "diseases": [self.disease_high.name],
            "locations": {"cities": [self.location_jakarta.city]},
        }
        qs = view._filtered_cases(filters)
        self.assertIn(self.case_with_news, qs)

    def test_filtered_cases_without_optional_filters(self):
        view = ExpertDashboardCSVDownloadAPIView()
        qs = view._filtered_cases({})
        self.assertGreaterEqual(qs.count(), 0)

    def test_csv_download_rejects_non_csv_format(self):
        payload = {
            "metric": "jumlah_kasus",
            "file_format": "png",
        }

        response = self.client.post(CSV_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], "Only CSV downloads are supported by this endpoint.")

    def test_csv_download_invalid_filters_returns_error(self):
        payload = {
            "metric": "jumlah_kasus",
            "filters": {
                "start_date": "2024-04-10",
                "end_date": "2024-04-01",
            },
        }

        response = self.client.post(CSV_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("filters", response.data["errors"])

    @override_settings(ENABLE_DOWNLOAD_LOGGING=True)
    def test_csv_download_handles_logging_failure(self):
        payload = {
            "metric": "jumlah_kasus",
            "file_format": "csv",
        }

        with patch("expert_user_feature.views.DashboardDownloadEventService.log_event", side_effect=Exception("db failure")):
            response = self.client.post(CSV_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["message"], "Download logging failed")

    def test_csv_download_defaults_file_format_when_missing(self):
        payload = {
            "metric": "jumlah_kasus",
            "filters": {"diseases": [self.disease_high.name]},
        }

        response = self.client.post(CSV_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        csv_rows = response.content.decode("utf-8").splitlines()
        self.assertTrue(csv_rows[0].startswith("case_id"))


class ExpertPermissionsTests(TestCase):
    def test_is_expert_user_role_checks_role(self):
        perm = IsExpertUserRole()
        request = SimpleNamespace(user=SimpleNamespace(role="EXP_USER"))
        self.assertTrue(perm.has_permission(request, None))

        request = SimpleNamespace(user=SimpleNamespace(role="CURATOR"))
        self.assertFalse(perm.has_permission(request, None))

        request = SimpleNamespace(user=None)
        self.assertFalse(perm.has_permission(request, None))

    def test_read_only_or_expert(self):
        perm = ReadOnlyOrExpert()

        read_request = SimpleNamespace(method="GET", user=None)
        self.assertTrue(perm.has_permission(read_request, None))

        write_request = SimpleNamespace(method="POST", user=SimpleNamespace(id=None, role="EXP_USER"))
        self.assertFalse(perm.has_permission(write_request, None))

        valid_request = SimpleNamespace(method="POST", user=SimpleNamespace(id=1, role="EXP_USER"))
        self.assertTrue(perm.has_permission(valid_request, None))


class ExpertSerializerTests(TestCase):
    def setUp(self):
        self.disease = Disease.objects.create(name="Leptospirosis", level_of_alertness=2)

    def _case_payload(self, *, news=None, location=None, **overrides):
        base_location = {
            "city": "Semarang",
            "province": "Jawa Tengah",
            "latitude": -6.9667,
            "longitude": 110.4167,
        }
        base_news = {
            "portal": "Portal X",
            "title": "Kasus Dilaporkan",
            "type": "artikel",
            "content": "Isi berita",
            "url": "https://example.com/news",
            "author": "Reporter X",
            "date_published": "2024-01-02T00:00:00Z",
            "img_url": "",
        }

        payload = {
            "disease": self.disease.name,
            "gender": "L",
            "age": 35,
            "city": "Semarang",
            "status": "biasa",
            "severity": "hospitalisasi",
            "location": dict(location or base_location),
            "news": dict(news or base_news),
        }

        payload.update(overrides)
        return payload

    def test_case_write_serializer_creates_case_and_news(self):
        payload = self._case_payload(news={
            "portal": "Portal X",
            "title": "Kasus Dilaporkan",
            "type": "artikel",
            "content": "Isi berita",
            "url": "https://example.com/news",
            "author": "Reporter X",
            "date_published": timezone.now(),
            "img_url": "",
        })

        serializer = CaseWriteSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        case = serializer.save()

        self.assertEqual(case.disease, self.disease)
        self.assertEqual(case.location.city, "Semarang")
        self.assertEqual(case.news.count(), 1)

    def test_expert_dashboard_download_serializer_rejects_invalid_filters(self):
        serializer = ExpertDashboardDownloadSerializer(
            data={"metric": "jumlah_kasus", "file_format": "csv", "filters": "not-a-dict"}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("filters", serializer.errors)

    def test_expert_dashboard_download_serializer_validates_source(self):
        serializer = ExpertDashboardDownloadSerializer(
            data={"metric": "jumlah_kasus", "file_format": "csv", "source": ""}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("source", serializer.errors)

    def test_expert_dashboard_download_serializer_allows_none_filters(self):
        serializer = ExpertDashboardDownloadSerializer()
        self.assertIsNone(serializer.validate_filters(None))

    def test_expert_dashboard_download_serializer_returns_source(self):
        serializer = ExpertDashboardDownloadSerializer()
        self.assertEqual(serializer.validate_source("dashboard"), "dashboard")

    def test_expert_dashboard_download_serializer_full_validation(self):
        serializer = ExpertDashboardDownloadSerializer(
            data={"metric": "jumlah_kasus", "file_format": "csv", "source": "dashboard"}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["source"], "dashboard")

    def test_expert_dashboard_download_serializer_blank_source_raises(self):
        serializer = ExpertDashboardDownloadSerializer()
        with self.assertRaises(serializers.ValidationError):
            serializer.validate_source("")

    def test_case_write_serializer_converts_naive_datetime(self):
        payload = self._case_payload(news={
            "portal": "Portal X",
            "title": "Tanggal Naive",
            "type": "artikel",
            "content": "Isi",
            "url": "https://example.com/naive",
            "author": "Reporter",
            "date_published": "2024-04-01T00:00:00",
            "img_url": "",
        })

        serializer = CaseWriteSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        case = serializer.save()
        news = case.news.first()
        self.assertFalse(timezone.is_naive(news.date_published))

    def test_case_write_serializer_fallback_on_invalid_datetime(self):
        payload = self._case_payload(news={
            "portal": "Portal X",
            "title": "Tanggal Invalid",
            "type": "artikel",
            "content": "Isi",
            "url": "https://example.com/invalid",
            "author": "Reporter",
            "date_published": "not-a-date",
            "img_url": "",
        })

        before = timezone.now()
        serializer = CaseWriteSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        case = serializer.save()
        news = case.news.first()
        self.assertGreaterEqual(news.date_published, before)
        self.assertFalse(timezone.is_naive(news.date_published))


class ExpertViewSmokeTests(SimpleTestCase):
    def test_get_serializer_class_returns_read_on_get(self):
        view = ExpertCaseCreateView()
        request = APIRequestFactory().get("/expert-feature/experts/cases/")
        view.request = request
        serializer_class = view.get_serializer_class()
        self.assertIs(serializer_class, CaseReadSerializer)

    def test_placeholder_endpoint_returns_200(self):
        client = APIClient()
        response = client.get("/expert-feature/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.content)
