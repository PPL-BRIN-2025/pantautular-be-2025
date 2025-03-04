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
        self.location1 = Location.objects.create(latitude=-6.9175, longitude=107.6191, name="Bandung")
        self.location2 = Location.objects.create(latitude=-6.2088, longitude=106.8456, name="Jakarta")

        self.case1 = Case.objects.create(
            id=uuid.uuid4(), gender="Female", age=25, city="Bandung", status="recovered",
            disease=self.disease, location=self.location1
        )
        self.case2 = Case.objects.create(
            id=uuid.uuid4(), gender="Male", age=30, city="Jakarta", status="confirmed",
            disease=self.disease, location=self.location2
        )
        
        self.case3 = Case.objects.create(
            id=uuid.uuid4(), gender="Male", age=40, city="Surabaya", status="deceased",
            disease=self.disease, location=None  
        )

    def test_get_all_case_locations(self):
        locations = list(CaseRepository.get_all_case_locations())
        self.assertEqual(len(locations), 2)
        expected_data = {
            str(self.case1.id): (float(self.location1.longitude), float(self.location1.latitude)),
            str(self.case2.id): (float(self.location2.longitude), float(self.location2.latitude)),
        }

        for case_data in locations:
            case_id = str(case_data["id"])
            self.assertIn(case_id, expected_data)

            expected_longitude, expected_latitude = expected_data[case_id]
            self.assertEqual(float(case_data["location__longitude"]), expected_longitude)
            self.assertEqual(float(case_data["location__latitude"]), expected_latitude)
