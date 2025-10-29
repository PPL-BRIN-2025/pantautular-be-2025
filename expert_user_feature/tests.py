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

 