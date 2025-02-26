from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .models import Case, Location, Disease
from .repositories import CaseRepository
from django.core.exceptions import ObjectDoesNotExist
import uuid
from unittest.mock import patch
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
                "latitude": f"{float(self.location.latitude):.6f}", 
                "longitude": f"{float(self.location.longitude):.6f}",
            }
        ]
        self.assertEqual(locations, expected)


    def test_get_all_case_locations_empty(self):
        Location.objects.all().delete() 

        locations = self.repository.get_all_case_locations()
        self.assertEqual(locations, [])

    @patch('pt_backend.models.Case.get_all_cases_locations', side_effect=ObjectDoesNotExist)
    def test_get_all_case_locations_exception(self, mock_get_all_cases_locations):
        result = self.repository.get_all_case_locations()
        self.assertEqual(result, {"error": "Error retrieving case locations"})


class CaseAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.disease1 = Disease.objects.create(name="Flu", level_of_alertness=2)
        self.disease2 = Disease.objects.create(name="COVID-19", level_of_alertness=5)

        self.case1 = Case.objects.create(
            id=uuid.uuid4(), gender="Male", age=30, city="Jakarta", status="confirmed", disease=self.disease1
        )
        self.case2 = Case.objects.create(
            id=uuid.uuid4(), gender="Female", age=25, city="Bandung", status="recovered", disease=self.disease2
        )

        self.location1 = Location.objects.create(latitude=-6.2088, longitude=106.8456, name="Jakarta", case=self.case1)
        self.location2 = Location.objects.create(latitude=-6.9175, longitude=107.6191, name="Bandung", case=self.case2)

    def test_get_all_case_locations(self):
        response = self.client.get('/cases/locations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [
            {"id": str(self.case1.id), "city": "Jakarta", "latitude": "-6.208800", "longitude": "106.845600"},
            {"id": str(self.case2.id), "city": "Bandung", "latitude": "-6.917500", "longitude": "107.619100"}
        ])

    def test_get_all_case_locations_empty(self):
        Location.objects.all().delete()  
        response = self.client.get('/cases/locations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])  

    @patch('pt_backend.repositories.CaseRepository.get_all_case_locations', side_effect=Exception("Database error"))
    def test_get_all_case_locations_exception(self, mock_get_all_case_locations):
        response = self.client.get('/cases/locations/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.json())