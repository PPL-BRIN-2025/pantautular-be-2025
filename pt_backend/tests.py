from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .models import Case, Location, Disease
from .repositories import CaseRepository
import uuid
# Create your tests here.

class CaseRepositoryTestCase(TestCase):
    def setUp(self):
        """Setup data sebelum setiap test dijalankan"""
        self.disease = Disease.objects.create(name="COVID-19", level_of_alertness=5)
        self.case = Case.objects.create(
            id=uuid.uuid4(),
            gender="Female",
            age=25,
            city="Bandung",
            status="recovered",
            disease=self.disease
        )
        self.location = Location.objects.create(
            latitude=-6.9175, longitude=107.6191, name="Bandung", case=self.case
        )
        self.repository = CaseRepository()

    def test_get_all_case_locations(self):
        """Test apakah repository dapat mengambil semua lokasi kasus"""
        locations = self.repository.get_all_case_locations()
        expected = [
            {
                "id": str(self.case.id),
                "city": "Bandung",
                "latitude": str(self.location.latitude),
                "longitude": str(self.location.longitude),
            }
        ]
        self.assertEqual(locations, expected)

