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
from rest_framework.test import APIClient

from pt_backend.models import Case, Disease, Location, News, User as PtUser


EXPERT_CASES_BASE = "/expert-feature/experts/cases/"


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

 