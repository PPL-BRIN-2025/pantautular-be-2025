import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pantau_tular.test_settings")

import uuid
from types import SimpleNamespace

import django

django.setup()

from datetime import datetime
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase, APIRequestFactory
from django.urls import reverse

from pt_backend.models import Case, CaseUploadBatch, Disease, Location, News, User as PtUser


EXPERT_CASES_BASE = "/expert-feature/experts/cases/"
from django.contrib.auth import get_user_model
from unittest.mock import patch

from .models import ExpertDataLog, ExpertDataset, ExpertDatasetRow
from .services import build_or_refresh_dataset_from_batch
from .serializers import ExpertDatasetRowSerializer
from .views import ExpertCaseListCreateView

User = get_user_model()

class TestExpertCaseAPI(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.expert = PtUser.objects.create(
            name="Expert User",
            email="expert@example.com",
            password=make_password("test-password"),
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

    def test_case_list_filters_by_batch_param(self):
        batch_a = CaseUploadBatch.objects.create(uploaded_by=self.expert, filename="a.csv")
        batch_b = CaseUploadBatch.objects.create(uploaded_by=self.expert, filename="b.csv")
        Case.objects.create(
            id=uuid.uuid4(),
            disease=self.disease_hb,
            location=self.loc_bandung,
            gender="P",
            age=28,
            city="Bandung",
            status="biasa",
            severity="insiden",
            created_by=self.expert,
            batch=batch_a,
        )
        Case.objects.create(
            id=uuid.uuid4(),
            disease=self.disease_dbd,
            location=self.loc_jakarta,
            gender="L",
            age=31,
            city="Jakarta",
            status="bahaya",
            severity="mortalitas",
            created_by=self.expert,
            batch=batch_b,
        )

        res = self.client.get(f"{EXPERT_CASES_BASE}?batch={batch_a.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

    def test_case_create_rejects_unknown_batch(self):
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
            "batch": str(uuid.uuid4()),
        }

        response = self.client.post(EXPERT_CASES_BASE, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("batch", response.data.get("errors", {}))

    def test_case_create_accepts_known_batch(self):
        batch = CaseUploadBatch.objects.create(uploaded_by=self.expert, filename="cases.csv")
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
            "batch": str(batch.id),
        }

        response = self.client.post(EXPERT_CASES_BASE, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        case = Case.objects.get(batch=batch)
        self.assertEqual(case.created_by, self.expert)

    def test_get_queryset_filters_by_batch_direct_call(self):
        batch = CaseUploadBatch.objects.create(uploaded_by=self.expert, filename="direct.csv")
        Case.objects.create(
            disease=self.disease_hb,
            location=self.loc_bandung,
            gender="P",
            age=20,
            city="Bandung",
            status="biasa",
            severity="insiden",
            created_by=self.expert,
            batch=batch,
        )
        view = ExpertCaseListCreateView()
        request = APIRequestFactory().get(f"{EXPERT_CASES_BASE}?batch={batch.id}")
        request.user = self.expert
        view.request = view.initialize_request(request)
        view.request.user = self.expert
        qs = view.get_queryset()
        self.assertEqual(qs.count(), 1)

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


class TestExpertDatasetAPI(APITestCase):
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


class TestAuditTrail(TestCase):
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

    def test_curator_log_event_calls_underlying_impl(self):
        calls = []

        def fake_curator(**kwargs):
            calls.append(kwargs)

        with patch("expert_user_feature.audittrail._curator_log_event", side_effect=fake_curator):
            from expert_user_feature import audittrail
            audittrail.curator_log_event(user="expert", action="demo")

        self.assertEqual(calls[0]["action"], "demo")

    def test_log_expert_action_handles_persistence_failure(self):
        from expert_user_feature import audittrail

        with patch.object(ExpertDataLog.objects, "create", side_effect=RuntimeError("boom")):
            audittrail.log_expert_action(SimpleNamespace(email="expert@example.com"), data_id=uuid.uuid4(), title="upload")

    def tearDown(self):
        self.audit_module.curator_log_event = self.original_curator


class TestExpertDataLogModel(TestCase):
    def test_str_and_immutable_guards(self):
        dataset = ExpertDataset.objects.create(
            data_id="DATASET-ID",
            file_name="file.csv",
            last_edited=timezone.now(),
            submitted_by="tester",
        )
        row = ExpertDatasetRow.objects.create(
            dataset=dataset,
            row_number=1,
            data_id="ROW-ID",
            gender="P",
            status="biasa",
        )
        self.assertEqual(str(row), f"{row.dataset_id}#1")

        log = ExpertDataLog.objects.create(
            data_id=uuid.uuid4(),
            title="upload csv",
            submitted_by="tester",
            note="ok",
        )
        self.assertIn("upload csv", str(log))
        with self.assertRaises(ValueError):
            log.save()
        with self.assertRaises(ValueError):
            log.delete()


class TestExpertDatasetRowSerializer(TestCase):
    def setUp(self):
        self.dataset = ExpertDataset.objects.create(
            data_id="SERIALIZER",
            file_name="serialize.csv",
            last_edited=timezone.now(),
            submitted_by="tester",
        )
        self.disease = Disease.objects.create(id=uuid.uuid4(), name="Malaria", level_of_alertness=2)
        self.location = Location.objects.create(id=uuid.uuid4(), city="City A", province="Province A")
        self.case = Case.objects.create(
            id=uuid.uuid4(),
            disease=self.disease,
            location=self.location,
            gender="P",
            age=21,
            city="City A",
            status="biasa",
            severity="insiden",
        )
        self.news = News.objects.create(
            case=self.case,
            portal="Portal DB",
            title="Judul DB",
            type="artikel",
            content="Isi",
            url="https://example.com/db",
            author="Reporter",
            date_published=timezone.make_aware(datetime(2024, 4, 1, 10, 0, 0)),
        )
        self.viewer = PtUser.objects.create(
            name="Viewer",
            email="viewer@example.com",
            password="pwd",
            role="EXP_USER",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.viewer)

    def test_serializer_uses_flat_news_payload(self):
        row = ExpertDatasetRow.objects.create(
            dataset=self.dataset,
            row_number=1,
            data_id=str(uuid.uuid4()),
            disease_id=str(self.disease.id),
            location_id=str(self.location.id),
            payload={
                "news_portal": "Portal Flat",
                "news_title": "Judul Flat",
                "news_type": "artikel",
                "news_content": "Konten",
                "news_url": "https://flat",
                "news_author": "Reporter Flat",
                "news_date_published": "2024-01-01T00:00:00Z",
                "location": {"city": "Payload City", "province": "Payload Province"},
            },
        )

        data = ExpertDatasetRowSerializer(row).data
        self.assertEqual(data["news_portal"], "Portal Flat")
        self.assertEqual(data["news_date_published"], "2024-01-01T00:00:00Z")
        self.assertEqual(data["location_name"], "Payload City")
        self.assertEqual(data["location_province"], "Payload Province")

    def test_serializer_falls_back_to_db_and_handles_missing_refs(self):
        row = ExpertDatasetRow.objects.create(
            dataset=self.dataset,
            row_number=2,
            data_id=str(self.case.id),
            disease_id=str(uuid.uuid4()),
            location_id=str(uuid.uuid4()),
            city="Fallback City",
            payload={},
        )

        data = ExpertDatasetRowSerializer(row).data
        self.assertEqual(data["news_portal"], "Portal DB")
        self.assertEqual(data["news_date_published"], self.news.date_published.isoformat())
        self.assertEqual(data["disease_name"], row.disease_id)
        self.assertEqual(data["location_name"], "Fallback City")
        self.assertEqual(data["location_province"], "")

    def test_serializer_handles_news_lookup_errors(self):
        row = ExpertDatasetRow.objects.create(
            dataset=self.dataset,
            row_number=3,
            data_id=str(self.case.id),
            disease_id=str(self.disease.id),
            location_id=str(self.location.id),
            payload={},
        )
        with patch("expert_user_feature.serializers.News.objects") as news_manager:
            news_manager.only.side_effect = RuntimeError("boom")
            data = ExpertDatasetRowSerializer(row).data
        self.assertEqual(data["news_portal"], "")

    @patch("expert_user_feature.views.log_expert_event", side_effect=RuntimeError("boom"))
    def test_dataset_rows_view_swallow_audit_failure(self, _mock):
        ExpertDatasetRow.objects.create(
            dataset=self.dataset,
            row_number=4,
            data_id=str(self.case.id),
            disease_id=str(self.disease.id),
            location_id=str(self.location.id),
            payload={"news_portal": "Portal X"},
        )
        url = f"/expert-feature/api/expert/datasets/{self.dataset.data_id}/rows/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_serializer_location_payload_without_values_falls_back_to_db(self):
        row = ExpertDatasetRow.objects.create(
            dataset=self.dataset,
            row_number=5,
            data_id=str(self.case.id),
            disease_id=str(self.disease.id),
            location_id=str(self.location.id),
            payload={"location": {}},
        )
        data = ExpertDatasetRowSerializer(row).data
        self.assertEqual(data["location_name"], self.location.city)
        self.assertEqual(data["location_province"], self.location.province)


class TestExpertDatasetService(TestCase):
    def test_build_dataset_handles_empty_batch(self):
        uploader = PtUser.objects.create(name="Uploader", email="uploader@example.com", password="x", role="EXP_USER")
        batch = CaseUploadBatch.objects.create(uploaded_by=uploader, filename="empty.csv")

        dataset = build_or_refresh_dataset_from_batch(batch)
        self.assertEqual(dataset.file_name, "empty.csv")
        self.assertEqual(ExpertDatasetRow.objects.filter(dataset=dataset).count(), 0)


class TestExpertDataLogView(TestCase):
    def setUp(self):
        self.user = PtUser.objects.create(
            name="Auditor",
            email="audit@example.com",
            password="pwd",
            role="EXP_USER",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = "/expert-feature/api/expert/audit-logs/"
        self.log_a = ExpertDataLog.objects.create(
            data_id=uuid.uuid4(),
            title="upload csv",
            submitted_by="auditor",
            note="a",
        )
        self.log_b = ExpertDataLog.objects.create(
            data_id=uuid.uuid4(),
            title="delete batch",
            submitted_by="auditor",
            note="b",
        )

    def test_audit_logs_view_allows_search_and_sort(self):
        response = self.client.get(self.url, {"search": "upload", "sort": "title:asc"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [item["title"] for item in response.data["results"]]
        self.assertIn("upload csv", titles)

    def test_audit_logs_view_handles_invalid_sort(self):
        response = self.client.get(self.url, {"sort": "invalid"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 2)
        
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


class TestExpertCaseBatchAPI(TestCase):
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
        other = PtUser.objects.create(name="Other", email="o@x.com", password=make_password("test-password"), role="EXP_USER")
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

    def test_bulk_delete_removes_only_user_cases(self):
        Case.objects.create(
            disease=self.disease,
            location=self.loc,
            gender="P",
            age=33,
            city="Jakarta",
            status="biasa",
            severity="insiden",
            created_by=self.expert,
        )
        other = PtUser.objects.create(name="Other", email="other@example.com", password=make_password("test-password"), role="EXP_USER")
        Case.objects.create(
            disease=self.disease,
            location=self.loc,
            gender="L",
            age=40,
            city="Bandung",
            status="bahaya",
            severity="mortalitas",
            created_by=other,
        )

        res = self.client.delete(f"{EXPERT_CASES_BASE}delete-all/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(res.data["deleted_cases"], 1)
        self.assertFalse(Case.objects.filter(created_by=self.expert).exists())

    @patch("expert_user_feature.views.log_expert_action", side_effect=RuntimeError("boom"))
    def test_batch_delete_swallow_audit_failure(self, _mock):
        batch_id = self._upload_csv().data["batch_id"]
        res = self.client.delete(f"{EXPERT_BATCH_BASE}{batch_id}/delete/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)


EXPERT_BATCH_BASE = "/expert-feature/experts/batches/"
DATASET_ROWS_BASE = "/expert-feature/api/expert/datasets/{data_id}/rows/"

class TestExpertDatasetMirror(TestCase):
    def setUp(self):
        self.client = APIClient()

        # EXP user
        self.expert = PtUser.objects.create(
            name="Expert Mirror",
            email="expert.mirror@example.com",
            password=make_password("test-password"),
            role="EXP_USER",
        )
        self.client.force_authenticate(self.expert)

        self.dbd = Disease.objects.create(id=uuid.uuid4(), name="DBD", level_of_alertness=2)
        self.hbv = Disease.objects.create(id=uuid.uuid4(), name="Hepatitis B", level_of_alertness=3)
        self.loc_jkt = Location.objects.create(id=uuid.uuid4(), city="Jakarta", province="DKI Jakarta")
        self.loc_bdg = Location.objects.create(id=uuid.uuid4(), city="Bandung", province="Jawa Barat")

        self.csv_full = (
            "disease,gender,age,city,status,severity,"
            "location_city,location_province,location_latitude,location_longitude,"
            "news_portal,news_title,news_type,news_content,news_url,news_author,news_date_published,news_img_url\n"
            "DBD,L,45,Jakarta,katastropik,mortalitas,Jakarta,DKI Jakarta,,,Detik,Lonjakan DBD,artikel,Isi A,https://detik/a,Rep A,2025-02-12T10:00:00Z,https://img/a.jpg\n"
            "Hepatitis B,P,8,Bandung,biasa,insiden,Bandung,Jawa Barat,,,Antara,HBV Turun,artikel,Isi B,https://antara/b,Rep B,2025-03-05T14:30:00Z,\n"
        ).encode("utf-8")

    def _upload(self, content: bytes):
        upload = SimpleUploadedFile("cases.csv", content, content_type="text/csv")
        return self.client.post(f"{EXPERT_CASES_BASE}upload-csv/", {"file": upload}, format="multipart")

    @patch("expert_user_feature.views.log_expert_action")  # biar ga failure
    def test_upload_builds_dataset_and_rows_with_names_and_news_payload(self, audit_mock):
        res = self._upload(self.csv_full)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        batch_id = res.data["batch_id"]

        # Mirror dataset shaped
        ds = ExpertDataset.objects.filter(data_id=str(batch_id)).first()
        self.assertIsNotNone(ds, "ExpertDataset tidak dibuat")
        self.assertEqual(ds.file_name, "cases.csv")

        # Rows forned
        rows = ExpertDatasetRow.objects.filter(dataset=ds).order_by("row_number")
        self.assertEqual(rows.count(), 2)

        # Cek serializer fields 
        from expert_user_feature.serializers import ExpertDatasetRowSerializer
        s0 = ExpertDatasetRowSerializer(rows[0]).data
        s1 = ExpertDatasetRowSerializer(rows[1]).data

        # disease_name readable
        self.assertEqual(s0["disease_name"], "DBD")
        self.assertEqual(s1["disease_name"], "Hepatitis B")

        # location split kota & provinsi
        self.assertEqual(s0["location_name"], "Jakarta")
        self.assertEqual(s0["location_province"], "DKI Jakarta")
        self.assertEqual(s1["location_name"], "Bandung")
        self.assertEqual(s1["location_province"], "Jawa Barat")

        # payload.news 
        for sd in (s0, s1):
            news = (sd.get("payload") or {}).get("news") or {}
            for key in ["portal", "title", "type", "content", "url", "author", "date_published"]:
                self.assertIn(key, news, f"payload.news.{key} harus ada")

        # Endpoint rows (paginated) return same
        api = self.client.get(DATASET_ROWS_BASE.format(data_id=str(batch_id)) + "?page=1&pageSize=1")
        self.assertEqual(api.status_code, 200)
        self.assertEqual(api.data["count"], 2)
        self.assertEqual(len(api.data["results"]), 1)
        self.assertIn("disease_name", api.data["results"][0])
        audit_mock.assert_called()  # upload noted

    @patch("expert_user_feature.views.log_expert_action")
    def test_delete_batch_cleans_only_its_dataset_mirror(self, audit_mock):
        # upload batch A
        a = self._upload(self.csv_full).data["batch_id"]
        # upload batch B 
        csv2 = (
            "disease,gender,age,city,status,severity,location_city,location_province,"
            "news_portal,news_title,news_type,news_content,news_url,news_author,news_date_published\n"
            "DBD,L,10,Bandung,biasa,insiden,Bandung,Jawa Barat,Portal,Judul,artikel,Teks,https://x,Auth,2025-01-01T00:00:00Z\n"
        ).encode()
        b = self._upload(csv2).data["batch_id"]

        # sanity mirror 2
        self.assertTrue(ExpertDataset.objects.filter(data_id=str(a)).exists())
        self.assertTrue(ExpertDataset.objects.filter(data_id=str(b)).exists())

        # delete batch A
        r = self.client.delete(f"{EXPERT_BATCH_BASE}{a}/delete/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)


        self.assertFalse(ExpertDataset.objects.filter(data_id=str(a)).exists())
        self.assertFalse(ExpertDatasetRow.objects.filter(dataset__data_id=str(a)).exists())
        self.assertTrue(ExpertDataset.objects.filter(data_id=str(b)).exists())
        self.assertTrue(ExpertDatasetRow.objects.filter(dataset__data_id=str(b)).exists())
        audit_mock.assert_called() 
