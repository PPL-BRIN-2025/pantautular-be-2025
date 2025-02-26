from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from models import Case, Disease, Location
from repositories import CaseRepository
import uuid
# Create your tests here.

class CaseAPITest(TestCase):
    def set_up(self):
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
        
