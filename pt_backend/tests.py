from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .models import Case, Location, Disease
from .repositories import CaseRepository
from django.core.exceptions import ObjectDoesNotExist
import uuid
from unittest.mock import patch

class CaseRepositoryTestCase(TestCase):
    def setUp(self):
        self.disease = Disease.objects.create(name="COVID-19", level_of_alertness=5)
        self.location = Location.objects.create(
            latitude=-6.9175, longitude=107.6191, name="Bandung"
        )
        self.case = Case.objects.create(
            id=uuid.uuid4(),
            gender="Female",
            age=25,
            city="Bandung",
            status="recovered",
            disease=self.disease,
            location=self.location
        )

    def test_get_all_case_locations(self):
        locations = CaseRepository.get_all_case_locations()
        self.assertTrue(locations.exists())
        self.assertEqual(locations.count(), 1)
        case_data = locations.first()
        self.assertEqual(str(case_data["id"]), str(self.case.id))
        self.assertEqual(float(case_data["location__latitude"]), -6.9175)
        self.assertEqual(float(case_data["location__longitude"]), 107.6191)

    def test_get_all_case_locations_empty(self):
        Location.objects.all().delete() 
        locations = CaseRepository.get_all_case_locations()
        self.assertEqual(locations, [])
    
    @patch.object(Case, 'get_all_locations', side_effect=ObjectDoesNotExist)
    def test_get_all_case_locations_handles_object_does_not_exist(self, mock_get_all_cases_locations):
        locations = CaseRepository.get_all_case_locations()
        self.assertIsNone(locations)

class CaseAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.disease1 = Disease.objects.create(name="Flu", level_of_alertness=2)
        self.disease2 = Disease.objects.create(name="COVID-19", level_of_alertness=5)
        self.location1 = Location.objects.create(latitude=-6.2088, longitude=106.8456, name="Jakarta")
        self.location2 = Location.objects.create(latitude=-6.9175, longitude=107.6191, name="Bandung")
        self.case1 = Case.objects.create(
            id=uuid.uuid4(), gender="Male", age=30, city="Jakarta", status="confirmed", disease=self.disease1, location=self.location1
        )
        self.case2 = Case.objects.create(
            id=uuid.uuid4(), gender="Female", age=25, city="Bandung", status="recovered", disease=self.disease2, location=self.location2
        )


    def test_get_all_case_locations(self):
        response = self.client.get('/cases/locations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [
            {"id": str(self.case1.id), "location__latitude": "-6.208800", "location__longitude": "106.845600"},
            {"id": str(self.case2.id), "location__latitude": "-6.917500", "location__longitude": "107.619100"}
        ])
        
    def test_get_all_case_locations_empty(self):
        Location.objects.all().delete()  
        response = self.client.get('/cases/locations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), []) 

    