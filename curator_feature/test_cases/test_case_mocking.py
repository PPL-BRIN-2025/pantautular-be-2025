# tests/test_case_mocking.py

from unittest.mock import patch, Mock
from django.test import TestCase
from rest_framework.test import APIClient
from pt_backend.models import Case, Disease, Location, User
from django.contrib.auth.hashers import make_password

CASES_BASE = "/curator-feature/curator/cases/"

class CuratorCaseMockTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create a curator user (hash password to allow login if needed)
        self.curator = User.objects.create(
            name="Curator",
            email="curator@example.com",
            password=make_password("x"),
        )
        setattr(self.curator, "role", "CURATOR")
        self.curator.save()
        self.client.force_authenticate(self.curator)

        # Seed data
        self.disease = Disease.objects.create(name="DBD", level_of_alertness=3)
        self.location = Location.objects.create(
            city="Palangka Raya", province="Kalimantan Tengah",
            latitude=-2.1, longitude=113.9
        )

    @patch("curator_feature.serializers.News.objects.create")
    def test_create_case_when_news_creation_fails(self, mock_news_create):
        """
        ✅ Mock News failure — expect exception to be raised (no view changes needed)
        """
        mock_news_create.side_effect = Exception("DB write failed")

        payload = {
            "disease": "DBD",
            "gender": "L",
            "age": 10,
            "city": "Palangka Raya",
            "status": "bahaya",
            "severity": "insiden",
            "location": {"city": "Palangka Raya"},
            "news": {
                "portal": "Kompas",
                "title": "Kasus",
                "type": "artikel",
                "content": "isi berita",
                "url": "https://example.com",
                "author": "Reporter",
                "date_published": "2024-01-23T00:00:00Z",
                "img_url": "",
            },
        }

        # ✅ Expect serializer/view to raise an exception (since no error handling exists)
        with self.assertRaises(Exception):
            self.client.post(CASES_BASE, payload, format="json")

        mock_news_create.assert_called_once()



    @patch("curator_feature.serializers.Disease.objects.get")
    def test_create_case_mock_disease_not_found(self, mock_disease_get):
        """
        ✅ MOCK to isolate serializer logic from actual database.
        Simulate Disease lookup failure -> returns 400.
        """
        mock_disease_get.side_effect = Disease.DoesNotExist()

        payload = {
            "disease": "Unknown",
            "gender": "L",
            "age": 10,
            "city": "Palangka Raya",
            "status": "bahaya",
            "severity": "insiden",
            "location": {"city": "Palangka Raya"},
            "news": {
                "portal": "Kompas",
                "title": "Kasus X",
                "type": "artikel",
                "content": "C",
                "url": "https://example.com",
                "author": "A",
                "date_published": "2024-01-23T00:00:00Z",
                "img_url": "",
            },
        }

        response = self.client.post(CASES_BASE, payload, format="json")

        self.assertEqual(response.status_code, 400)
        mock_disease_get.assert_called_once()
