import uuid
from datetime import datetime, timezone
from django.test import TestCase
from rest_framework.test import APIClient
from pt_backend.models import Case, Disease, Location, News, User


CASES_BASE = "/curator-feature/curator/cases/"


class CuratorCaseAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # --- Users ---
        self.curator = User.objects.create(
            id=123456,
            name="Curator One",
            email="curator@example.com",
            password="x",
        )
        setattr(self.curator, "role", "CURATOR")
        self.curator.save()

        self.other_user = User.objects.create(
            id=789012,
            name="Viewer",
            email="viewer@example.com",
            password="x",
        )
        setattr(self.other_user, "role", "CONTRIBUTOR")
        self.other_user.save()

        # --- Seed master data ---
        self.disease_hb = Disease.objects.create(
            id=uuid.uuid4(), name="Hepatitis B", level_of_alertness=3
        )
        self.disease_dbd = Disease.objects.create(
            id=uuid.uuid4(), name="DBD", level_of_alertness=3
        )

        self.loc_palangka = Location.objects.create(
            id=uuid.uuid4(),
            city="Palangka Raya",
            province="Kalimantan Tengah",
            latitude=-2.156839,
            longitude=113.940011,
        )

        # Ambiguous city across provinces
        self.loc_sukabumi_jabar = Location.objects.create(
            id=uuid.uuid4(),
            city="Sukabumi",
            province="Jawa Barat",
            latitude=-6.906,
            longitude=106.928,
        )
        self.loc_sukabumi_dummy = Location.objects.create(
            id=uuid.uuid4(),
            city="Sukabumi",
            province="Jawa Barat (Kab.)",
            latitude=-6.934,
            longitude=106.925,
        )

    # ---------- helpers ----------
    def as_curator(self):
        self.client.force_authenticate(user=self.curator)

    def as_other(self):
        self.client.force_authenticate(user=self.other_user)

    def as_anon(self):
        # avoid logout signal issue by reinitializing client
        self.client = APIClient()

    # HAPPY PATH

    def test_create_case_with_existing_city_and_disease_name(self):
        """Create succeeds when disease and city exist; one News created."""
        self.as_curator()
        payload = {
            "disease": "Hepatitis B",
            "gender": "P",
            "age": 12,
            "city": "Palangka Raya",
            "status": "bahaya",
            "severity": "insiden",
            "location": {"city": "Palangka Raya"},
            "news": {
                "portal": "Kompas",
                "title": "Kasus Hepatitis Anak",
                "type": "artikel",
                "content": "Penyakit Hepatitis telah menyebar…",
                "url": "https://example.com/article",
                "author": "Reporter A",
                "date_published": "2024-01-23T00:00:00Z",
                "img_url": "",
            },
        }
        res = self.client.post(CASES_BASE, payload, format="json")
        self.assertEqual(res.status_code, 201, res.data)

        case = Case.objects.first()
        self.assertEqual(case.disease.name, "Hepatitis B")
        self.assertEqual(case.location.city, "Palangka Raya")
        self.assertEqual(case.status, "bahaya")
        self.assertEqual(case.severity, "insiden")
        self.assertEqual(News.objects.filter(case=case).count(), 1)

