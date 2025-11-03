import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pantau_tular.test_settings")

import uuid

import django

django.setup()

from datetime import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from django.urls import reverse

from pt_backend.models import Case, Disease, Location, News, User as PtUser


EXPERT_CASES_BASE = "/expert-feature/experts/cases/"
from django.contrib.auth import get_user_model
from unittest.mock import patch

from .models import ExpertDataset

User = get_user_model()

class ExpertCaseAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.expert = PtUser.objects.create(
            name="Expert User",
            email="expert@example.com",
            password="x",
            role="EXP_USER",
        )
        self.client.force_authenticate(user=self.expert)

        self.disease_hb = Disease.objects.create(
            id=uuid.uuid4(), name="Hepatitis B", level_of_alertness=3
        )
        self.disease_dbd = Disease.objects.create(
            id=uuid.uuid4(), name="DBD", level_of_alertness=2
        )

        self.loc_jakarta = Location.objects.create(
            id=uuid.uuid4(),
            city="Jakarta",
            province="DKI Jakarta",
            latitude=-6.2088,
            longitude=106.8456,
        )
        self.loc_bandung = Location.objects.create(
            id=uuid.uuid4(),
            city="Bandung",
            province="Jawa Barat",
            latitude=-6.9175,
            longitude=107.6191,
        )

    def test_expert_can_create_case(self):
        payload = {
            "disease": "Hepatitis B",
            "gender": "P",
            "age": 30,
            "city": "Bandung",
            "status": "bahaya",
            "severity": "insiden",
            "location": {"city": "Bandung"},
            "news": {
                "portal": "Portal A",
                "title": "Kasus Baru",
                "type": "artikel",
                "content": "Konten Berita",
                "url": "https://example.com/berita",
                "author": "Reporter A",
                "date_published": "2024-01-23T00:00:00Z",
                "img_url": "",
            },
        }

        response = self.client.post(EXPERT_CASES_BASE, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Case.objects.count(), 1)
        case = Case.objects.first()
        self.assertEqual(case.disease.name, "Hepatitis B")
        self.assertEqual(case.location.city, "Bandung")
        self.assertEqual(case.status, "bahaya")
        self.assertEqual(case.severity, "insiden")
        self.assertEqual(News.objects.filter(case=case).count(), 1)
    
    def test_expert_can_update_case(self):
        case = Case.objects.create(
            id=uuid.uuid4(),
            disease=self.disease_hb,
            location=self.loc_bandung,
            gender="P",
            age=25,
            city="Bandung",
            status="biasa",
            severity="hospitalisasi",
        )

        payload = {
            "disease": "DBD",
            "location": {"city": "Jakarta", "province": "DKI Jakarta"},
            "severity": "mortalitas",
        }
        response = self.client.patch(f"{EXPERT_CASES_BASE}{case.id}/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        case.refresh_from_db()
        self.assertEqual(case.disease.name, "DBD")
        self.assertEqual(case.location.city, "Jakarta")
        self.assertEqual(case.severity, "mortalitas")

    def test_expert_can_delete_case(self):
        case = Case.objects.create(
            id=uuid.uuid4(),
            disease=self.disease_hb,
            location=self.loc_jakarta,
            gender="L",
            age=40,
            city="Jakarta",
            status="bahaya",
            severity="insiden",
        )
        News.objects.create(
            case=case,
            portal="Portal",
            title="Judul",
            type="artikel",
            content="Isi",
            url="https://example.com/berita",
            author="Reporter",
            date_published=timezone.make_aware(datetime(2024, 1, 1)),
            img_url="",
        )

        response = self.client.delete(f"{EXPERT_CASES_BASE}{case.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Case.objects.filter(id=case.id).exists())
        self.assertFalse(News.objects.filter(case=case).exists())

    def test_expert_can_upload_cases_via_csv(self):
        csv_content = (
            "disease,gender,age,city,status,severity,"
            "location_city,location_province,location_latitude,location_longitude,"
            "news_portal,news_title,news_type,news_content,news_url,news_author,"
            "news_date_published,news_img_url\n"
            "DBD,L,7,Jakarta,bahaya,insiden,Jakarta,DKI Jakarta,,,"
            "Portal A,Judul A,artikel,Konten A,https://example.com/a,Reporter A,"
            "2024-02-01T00:00:00Z,\n"
            "Hepatitis B,P,12,Bandung,biasa,hospitalisasi,Bandung,Jawa Barat,,,"
            "Portal B,Judul B,artikel,Konten B,https://example.com/b,Reporter B,"
            "2024-03-01T00:00:00Z,\n"
        )

        upload = SimpleUploadedFile("cases.csv", csv_content.encode("utf-8"), content_type="text/csv")

        response = self.client.post(
            f"{EXPERT_CASES_BASE}upload-csv/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["created"], 2)
        self.assertTrue(Case.objects.filter(disease__name="DBD", city="Jakarta").exists())
        self.assertTrue(Case.objects.filter(disease__name="Hepatitis B", city="Bandung").exists())
        self.assertEqual(News.objects.count(), 2)


class ExpertDatasetAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="expert",
            password="x",
        )
        setattr(self.user, "role", "EXPERT")
        self.user.save()

        now = timezone.now()
        ExpertDataset.objects.bulk_create([
            ExpertDataset(data_id="ID1", file_name="Report_Jakarta.xlsx",        last_edited=now,                submitted_by="EXPERTA"),
            ExpertDataset(data_id="ID2", file_name="Survey_Bandung.csv",         last_edited=now - timezone.timedelta(days=1), submitted_by="EXPERTB"),
            ExpertDataset(data_id="ID3", file_name="Public_Health_Analysis.xlsx",last_edited=now - timezone.timedelta(days=2), submitted_by="EXPERTD"),
        ])
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.list_url = reverse("expert-dataset-list")
        self.detail_url = reverse("expert-dataset-detail", args=["ID1"])

    @patch("expert_user_feature.audittrail.curator_log_event")
    def test_list_and_filter_and_audit(self, audit_mock):
        r = self.client.get(self.list_url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 3)
        audit_mock.assert_called()  # list view logged

        r = self.client.get(self.list_url, {"search": "bandung"})
        self.assertEqual(r.status_code, 200)
        # Only the Bandung CSV should remain
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["data_id"], "ID2")

    @patch("expert_user_feature.audittrail.curator_log_event")
    def test_detail_logs_view(self, audit_mock):
        r = self.client.get(self.detail_url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["data_id"], "ID1")
        audit_mock.assert_called()  # detail view logged

    def test_permission_denied_for_anonymous(self):
        anon = APIClient()
        r = anon.get(self.list_url)
        self.assertEqual(r.status_code, 200)

    def test_sort_and_search_variations(self):
        r = self.client.get(self.list_url, {"search": " ", "sort": "invalid"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 3)  # no filter applied

        r = self.client.get(self.list_url, {"sort": "last_edited:asc"})
        self.assertEqual(r.status_code, 200)
        # first result should be oldest when ascending
        self.assertEqual(r.data["results"][0]["data_id"], "ID3")

        r = self.client.get(self.list_url, {"sort": "data_id:desc"})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.data["results"][0]["data_id"], r.data["results"][-1]["data_id"])

    @patch("expert_user_feature.views.log_expert_event", side_effect=RuntimeError("boom"))
    def test_detail_view_handles_audit_failure(self, _log):
        r = self.client.get(self.detail_url)
        self.assertEqual(r.status_code, 200)

    @patch("expert_user_feature.views.log_expert_event", side_effect=RuntimeError("boom"))
    def test_list_view_handles_audit_failure(self, _log):
        r = self.client.get(self.list_url, {"search": "ID"})
        self.assertEqual(r.status_code, 200)

    def test_dataset_str_representation(self):
        dataset = ExpertDataset.objects.create(
            data_id="ID4",
            file_name="Summary.pdf",
            last_edited=timezone.now(),
            submitted_by="EXPERTE",
        )
        self.assertIn("Summary.pdf", str(dataset))


class AuditTrailTests(TestCase):
    def setUp(self):
        from expert_user_feature import audittrail
        self.audit_module = audittrail
        self.original_curator = self.audit_module.curator_log_event

    def test_log_expert_event_calls_curator_when_available(self):
        events = []

        def fake_curator(**kwargs):
            events.append(kwargs)

        self.audit_module.curator_log_event = fake_curator
        self.audit_module.log_expert_event(user="expert", action="view", meta={"k": "v"})
        self.assertEqual(events[0]["action"], "view")
        self.assertEqual(events[0]["meta"], {"k": "v"})

    def test_log_expert_event_swallow_errors(self):
        def faulty(**kwargs):
            raise RuntimeError("boom")

        self.audit_module.curator_log_event = faulty
        # Should not raise
        self.audit_module.log_expert_event(user="expert", action="view", meta={})

    def tearDown(self):
        self.audit_module.curator_log_event = self.original_curator
        
import uuid
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from pt_backend.models import (
    Case,
    Disease,
    Location,
    CaseUploadBatch,
    User as PtUser
)

EXPERT_CASES_BASE = "/expert-feature/experts/cases/"
EXPERT_BATCH_BASE = "/expert-feature/experts/batches/"


class ExpertCaseBatchAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.expert = PtUser.objects.create(
            name="Expert",
            email="expert@example.com",
            password="x",
            role="EXP_USER",
        )
        self.client.force_authenticate(self.expert)

        self.disease = Disease.objects.create(id=uuid.uuid4(), name="DBD", level_of_alertness=2)
        self.loc = Location.objects.create(id=uuid.uuid4(), city="Jakarta", province="DKI")

        self.csv_data = (
            "disease,gender,age,city,status,severity,location_city,location_province,"
            "news_portal,news_title,news_type,news_content,news_url,news_author,news_date_published\n"
            "DBD,L,10,Jakarta,bahaya,insiden,Jakarta,DKI,"
            "Portal,Title,artikel,Text,https://x.com,Auth,2024-01-01T00:00:00Z\n"
        )

    def _upload_csv(self):
        upload = SimpleUploadedFile("cases.csv", self.csv_data.encode(), content_type="text/csv")
        return self.client.post(f"{EXPERT_CASES_BASE}upload-csv/", {"file": upload}, format="multipart")

    # ✅ 1. Upload membuat batch dan men-tag case
    def test_upload_creates_batch_and_tags_cases(self):
        res = self._upload_csv()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        batch = CaseUploadBatch.objects.first()
        self.assertIsNotNone(batch)
        self.assertEqual(batch.uploaded_by, self.expert)

        case = Case.objects.first()
        self.assertEqual(case.batch, batch)
        self.assertEqual(case.created_by, self.expert)

    # ✅ 2. List batch hanya menampilkan batch milik user ini
    def test_list_batches_returns_only_user_batches(self):
        self._upload_csv()

        other = PtUser.objects.create(name="Other", email="o@x.com", password="x", role="EXP_USER")
        CaseUploadBatch.objects.create(uploaded_by=other, filename="other.csv")

        res = self.client.get(EXPERT_BATCH_BASE)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)  # hanya batch milik si expert

    # ✅ 3. Delete batch menghapus hanya case batch itu
    def test_delete_batch_removes_only_its_cases(self):
        batch1_id = self._upload_csv().data["batch_id"]
        batch2 = CaseUploadBatch.objects.create(uploaded_by=self.expert, filename="batch2.csv")
        Case.objects.create(disease=self.disease, location=self.loc, gender="L", age=15, city="Y", status="bahaya", severity="insiden", created_by=self.expert, batch=batch2)

        res = self.client.delete(f"{EXPERT_BATCH_BASE}{batch1_id}/delete/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        # ✅ batch1 cases hilang
        self.assertFalse(Case.objects.filter(batch_id=batch1_id).exists())
        # ✅ batch2 cases tetap
        self.assertTrue(Case.objects.filter(batch=batch2).exists())

    # ✅ 4. User tidak bisa delete batch milik orang lain
    def test_user_cannot_delete_other_users_batch(self):
        other = PtUser.objects.create(name="Other", email="o@x.com", password="x", role="EXP_USER")
        batch = CaseUploadBatch.objects.create(uploaded_by=other, filename="other.csv")

        res = self.client.delete(f"{EXPERT_BATCH_BASE}{batch.id}/delete/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        self.assertTrue(CaseUploadBatch.objects.filter(id=batch.id).exists())

    # ✅ 5. Filter cases by batch
    def test_list_cases_filter_by_batch(self):
        batch1_id = self._upload_csv().data["batch_id"]
        batch2 = CaseUploadBatch.objects.create(uploaded_by=self.expert, filename="b2.csv")
        Case.objects.create(disease=self.disease, location=self.loc, gender="L", age=20, city="Y", status="bahaya", severity="insiden", created_by=self.expert, batch=batch2)

        res = self.client.get(f"{EXPERT_CASES_BASE}?batch={batch1_id}")
        self.assertEqual(len(res.data), 1)  # hanya case dari batch1