import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pantau_tular.test_settings")

import uuid

import django

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from expert_user_feature.views import ExpertCaseCSVUploadAPIView

from pt_backend.models import Case, Disease, Location, User as PtUser


CASE_BASE = "/expert-feature/experts/cases/"


class ExpertCaseErrorAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = PtUser.objects.create(
            name="Expert",
            email="expert@example.com",
            password="pwd",
            role="EXP_USER",
        )
        self.client.force_authenticate(user=self.user)

        self.disease = Disease.objects.create(name="Flu", level_of_alertness=1)
        self.other_disease = Disease.objects.create(name="DBD", level_of_alertness=3)

        self.location = Location.objects.create(city="City A", province="Province A")

        self.case = Case.objects.create(
            disease=self.disease,
            location=self.location,
            gender="P",
            age=30,
            city="City A",
            status="biasa",
            severity="insiden",
        )

    def test_patch_unknown_case_returns_404(self):
        response = self.client.patch(f"{CASE_BASE}{uuid.uuid4()}/", {"severity": "insiden"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_unknown_disease_returns_400(self):
        response = self.client.patch(
            f"{CASE_BASE}{self.case.id}/",
            {"disease": "Unknown Disease"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("disease", response.data.get("errors", {}))

    def test_patch_missing_location_city_returns_400(self):
        response = self.client.patch(
            f"{CASE_BASE}{self.case.id}/",
            {"location": {"province": "Province B"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("location", response.data.get("errors", {}))

    def test_patch_without_location_updates_fields(self):
        response = self.client.patch(
            f"{CASE_BASE}{self.case.id}/",
            {"status": "bahaya", "severity": "mortalitas"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, "bahaya")
        self.assertEqual(self.case.severity, "mortalitas")

    def test_patch_updates_existing_location_metadata(self):
        response = self.client.patch(
            f"{CASE_BASE}{self.case.id}/",
            {
                "disease": self.other_disease.name,
                "location": {
                    "city": self.location.city,
                    "province": "Updated Province",
                    "latitude": "1.23",
                    "longitude": "4.56",
                },
                "status": "bahaya",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.case.refresh_from_db()
        self.assertEqual(self.case.location.province, "Updated Province")
        self.assertEqual(self.case.status, "bahaya")
        self.assertEqual(self.case.disease, self.other_disease)

    def test_patch_creates_new_location(self):
        response = self.client.patch(
            f"{CASE_BASE}{self.case.id}/",
            {
                "location": {"city": "New City", "province": "Province B"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.case.refresh_from_db()
        self.assertEqual(self.case.location.city, "New City")
        self.assertTrue(Location.objects.filter(city="New City").exists())

    def test_delete_unknown_case_returns_404(self):
        response = self.client.delete(f"{CASE_BASE}{uuid.uuid4()}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_csv_upload_requires_file(self):
        response = self.client.post(f"{CASE_BASE}upload-csv/", {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data.get("errors", {}))

    def test_csv_upload_decode_error(self):
        upload = SimpleUploadedFile("cases.csv", bytes([0xFF]), content_type="text/csv")
        response = self.client.post(f"{CASE_BASE}upload-csv/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data.get("errors", {}))

    def test_csv_upload_requires_header(self):
        upload = SimpleUploadedFile("cases.csv", "".encode("utf-8"), content_type="text/csv")
        response = self.client.post(f"{CASE_BASE}upload-csv/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data.get("errors", {}))

    def test_csv_upload_reports_row_errors(self):
        csv_content = (
            "disease,gender,age,city,status,severity,"
            "location_city,location_province,location_latitude,location_longitude,"
            "news_portal,news_title,news_type,news_content,news_url,news_author,"
            "news_date_published,news_img_url\n"
            ",L,7,City A,bahaya,insiden,City A,Province A,,,Portal,Title,artikel,Content,"
            "https://example.com,Reporter,2024-02-01T00:00:00Z,\n"
        )
        upload = SimpleUploadedFile("cases.csv", csv_content.encode("utf-8"), content_type="text/csv")

        response = self.client.post(f"{CASE_BASE}upload-csv/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)
        self.assertEqual(Case.objects.count(), 1)

    def test_clean_decimal_helper(self):
        view = ExpertCaseCSVUploadAPIView()
        self.assertIsNone(view._clean_decimal(None))
        self.assertIsNone(view._clean_decimal(" "))
        self.assertEqual(view._clean_decimal(" 1.23 "), "1.23")

    def test_csv_upload_handles_missing_header_row(self):
        upload = SimpleUploadedFile("cases.csv", b"disease,gender\n", content_type="text/csv")
        dummy_reader = type("R", (), {"fieldnames": None})()
        with patch("expert_user_feature.views.csv.DictReader", return_value=dummy_reader):
            response = self.client.post(f"{CASE_BASE}upload-csv/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data.get("errors", {}))

    def test_csv_upload_reports_missing_columns(self):
        csv_content = "disease,gender\nDBD,L\n"
        upload = SimpleUploadedFile("cases.csv", csv_content.encode("utf-8"), content_type="text/csv")
        response = self.client.post(f"{CASE_BASE}upload-csv/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data.get("errors", {}))

    def test_csv_upload_handles_unexpected_error(self):
        csv_content = (
            "disease,gender,age,city,status,severity,location_city,location_province,"
            "news_portal,news_title,news_type,news_content,news_url,news_author,news_date_published\n"
            "DBD,L,9,City,biasa,insiden,City,Province,Portal,Title,artikel,Content,https://example.com,Author,2024-01-01T00:00:00Z\n"
        )
        upload = SimpleUploadedFile("cases.csv", csv_content.encode("utf-8"), content_type="text/csv")
        with patch("expert_user_feature.views.CaseWriteSerializer.save", side_effect=RuntimeError("boom")):
            response = self.client.post(f"{CASE_BASE}upload-csv/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], "Failed to import CSV")

    @patch("expert_user_feature.views.log_expert_action", side_effect=RuntimeError("audit fail"))
    @patch("expert_user_feature.views.build_or_refresh_dataset_from_batch", side_effect=RuntimeError("sync fail"))
    def test_csv_upload_swallow_downstream_failures(self, *_mocks):
        csv_content = (
            "disease,gender,age,city,status,severity,"
            "location_city,location_province,location_latitude,location_longitude,"
            "news_portal,news_title,news_type,news_content,news_url,news_author,news_date_published\n"
            "DBD,L,10,City,biasa,insiden,City,Province,-6.2,106.8,Portal,Title,artikel,Content,https://example.com,Author,2024-01-01T00:00:00Z\n"
        )
        upload = SimpleUploadedFile("cases.csv", csv_content.encode("utf-8"), content_type="text/csv")
        response = self.client.post(f"{CASE_BASE}upload-csv/", {"file": upload}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_convert_includes_lat_lon_when_present(self):
        view = ExpertCaseCSVUploadAPIView()
        row = {
            "disease": self.disease.name,
            "gender": "P",
            "age": "33",
            "city": "City A",
            "status": "biasa",
            "severity": "insiden",
            "location_city": "City A",
            "location_province": "Province A",
            "location_latitude": "1.234",
            "location_longitude": "5.678",
            "news_portal": "Portal",
            "news_title": "Title",
            "news_type": "artikel",
            "news_content": "Content",
            "news_url": "https://example.com",
            "news_author": "Reporter",
            "news_date_published": "2024-01-01T00:00:00Z",
            "news_img_url": "",
        }
        data = view._convert(row)
        self.assertEqual(data["location"]["latitude"], "1.234")
        self.assertEqual(data["location"]["longitude"], "5.678")
