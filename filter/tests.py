from django.test import TestCase

# Create your tests here.
from django.test import TestCase
from pt_backend.models import Disease
from pt_backend.repositories import DiseaseRepository
from django.core.exceptions import ObjectDoesNotExist
import uuid
from unittest.mock import patch
# Create your tests here.

class DiseaseRepositoryTestCase(TestCase):
    def setUp(self):
        """Setup data sebelum setiap test dijalankan"""
        self.disease1 = Disease.objects.create(
            id=uuid.uuid4(), name="COVID-19", level_of_alertness=5
        )
        self.disease2 = Disease.objects.create(
            id=uuid.uuid4(), name="Ebola", level_of_alertness=4
        )
        self.repository = DiseaseRepository()

    def test_get_all_diseases_name(self):
        """Test apakah repository dapat mengambil semua nama penyakit"""
        diseases = self.repository.get_all_diseases_name()
        expected = ["COVID-19", "Ebola"]
        self.assertEqual(diseases, expected)

    def test_get_all_diseases_name_empty(self):
        Disease.objects.all().delete()  

        diseases = self.repository.get_all_diseases_name()
        self.assertEqual(diseases, [])

    @patch('pt_backend.models.Disease.get_all_diseases', side_effect=ObjectDoesNotExist)
    def test_get_all_diseases_name_exception(self, mock_get_all_diseases):
        result = self.repository.get_all_diseases_name()
        self.assertEqual(result, {"error": "Error retrieving diseases"})