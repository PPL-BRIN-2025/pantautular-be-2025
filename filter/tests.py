from django.test import TestCase

# Create your tests here.
from django.test import TestCase
from pt_backend.models import Case, Disease, Location, News
from pt_backend.repositories import DiseaseRepository, LocationRepository, NewsRepository
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

class LocationRepositoryTestCase(TestCase):
    def setUp(self):
        """Setup data sebelum setiap test dijalankan"""
        self.disease = Disease.objects.create(name="COVID-19", level_of_alertness=5)
        self.case = Case.objects.create(
            id=uuid.uuid4(),
            gender="Pria",
            age=30,
            city="Jakarta",
            status="recovered",
            disease=self.disease
        )
        self.location1 = Location.objects.create(
            latitude=-6.2088, longitude=106.8456, name="Jakarta", case=self.case
        )
        self.location2 = Location.objects.create(
            latitude=-6.9175, longitude=107.6191, name="Bandung", case=self.case
        )
        self.repository = LocationRepository()

    def test_get_all_locations_name(self):
        locations = self.repository.get_all_locations_name()
        expected = ["Jakarta", "Bandung"]
        self.assertEqual(locations, expected)

    def test_get_all_locations_name_empty(self):
        Location.objects.all().delete()  

        locations = self.repository.get_all_locations_name()
        self.assertEqual(locations, [])

    @patch('pt_backend.models.Location.get_all_locations', side_effect=ObjectDoesNotExist)
    def test_get_all_locations_name_exception(self, mock_get_all_locations):
        result = self.repository.get_all_locations_name()
        self.assertEqual(result, {"error": "Error retrieving locations"})

class NewsRepositoryTestCase(TestCase):
    def setUp(self):
        self.news1 = News.objects.create(
            portal="kompas.com",
            news_type="health",
            content="COVID-19 Detected in Jakarta",
            url="https://www.kompas.com/covid-jakarta",
            author="Dr. Joko",
            title="COVID-19 case detected in Jakarta...",
            release_date="2025-03-01 00:00:00+00"
        )
        self.news2 = News.objects.create(
            portal="detik.com",
            news_type="health",
            content="SARS Detected in Medan",
            url="https://www.detik.com/sars-medan",
            author="Dr. Sari",
            title="SARS case detected in Medan...",
            release_date="2025-03-01 00:00:00+00"
        )
        self.repository = NewsRepository()

    def test_get_all_news_name(self):
        news = self.repository.get_all_news_name()
        expected = ["kompas.com", "detik.com"]
        self.assertEqual(news, expected)

    def test_get_all_news_name_empty(self):
        News.objects.all().delete()  

        news = self.repository.get_all_news_name()
        self.assertEqual(news, [])

    @patch('pt_backend.models.News.get_all_news', side_effect=ObjectDoesNotExist)
    def test_get_all_news_name_exception(self, mock_get_all_news):
        result = self.repository.get_all_news_name()
        self.assertEqual(result, {"error": "Error retrieving news"})