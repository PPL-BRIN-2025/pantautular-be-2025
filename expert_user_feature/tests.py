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