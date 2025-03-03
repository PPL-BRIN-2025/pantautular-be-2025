from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

# Create your tests here.
from django.test import TestCase
from pt_backend.models import Case, Disease, Location, News
from pt_backend.repositories import DiseaseRepository, LocationRepository, NewsRepository
from django.core.exceptions import ObjectDoesNotExist
import uuid
from unittest.mock import patch

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

class FiltersViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('pt_backend.repositories.DiseaseRepository.get_all_diseases_name', side_effect=ObjectDoesNotExist)
    def test_get_filters_diseases_not_found(self, mock_get_all_diseases_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"error": "No diseases found"})

class FilterAPITest(TestCase):
    def setUp(self):
        """Setup data sebelum test dijalankan"""
        self.client = APIClient()
        self.diseaseRepository = DiseaseRepository()
        self.locationRepository = LocationRepository()
        self.newsRepository = NewsRepository()

        self.disease1 = Disease.objects.create(name="COVID-19", level_of_alertness=5)
        self.disease2 = Disease.objects.create(name="Ebola", level_of_alertness=4)

        self.case1 = Case.objects.create(
            id=1, gender="Male", age=30, city="Jakarta", status="kematian", disease=self.disease1
        )
        self.case2 = Case.objects.create(
            id=2, gender="Female", age=25, city="Bandung", status="terjangkit", disease=self.disease2
        )

        self.location1 = Location.objects.create(latitude=-6.2088, longitude=106.8456, name="Jakarta", case_id=self.case1.id)
        self.location2 = Location.objects.create(latitude=-6.9175, longitude=107.6191, name="Bandung", case_id=self.case2.id)

        #     portal, news_type , content , url ,author ,title ,release_date 
        self.news1 = News.objects.create(
            portal="kompas.com", news_type="health", content="COVID-19 Detected in Jakarta", url="https://www.kompas.com/covid-jakarta", author="Dr. Joko", title="COVID-19 case detected in Jakarta...", release_date="2025-03-01 00:00:00+00"
        )
        self.news2 = News.objects.create(
            portal="detik.com", news_type="health", content="SARS Detected in Medan", url="https://www.detik.com/sars-medan", author="Dr. Sari", title="SARS case detected in Medan...", release_date="2025-03-01 00:00:00+00"
        )

    def test_get_filters(self):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {
            "diseases": ["COVID-19", "Ebola"],
            "locations": ["Jakarta", "Bandung"],
            "news": ["kompas.com", "detik.com"]
        })
    
    def test_get_filters_empty(self):
        Disease.objects.all().delete()
        Location.objects.all().delete()
        News.objects.all().delete()

        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {
            "diseases": [],
            "locations": [],
            "news": []
        })

    @patch('pt_backend.repositories.DiseaseRepository.get_all_diseases_name', side_effect=ObjectDoesNotExist)
    def test_get_filters_exception(self, mock_get_all_diseases_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"error": "No diseases found"})
    
    @patch('pt_backend.repositories.DiseaseRepository.get_all_diseases_name', side_effect=Exception("Database error"))
    def test_get_filters_exception(self, mock_get_all_diseases_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.json())

    @patch('pt_backend.repositories.LocationRepository.get_all_locations_name', side_effect=ObjectDoesNotExist)
    def test_get_filters_exception(self, mock_get_all_locations_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"error": "No locations found"})
    
    @patch('pt_backend.repositories.LocationRepository.get_all_locations_name', side_effect=Exception("Database error"))
    def test_get_filters_exception(self, mock_get_all_locations_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.json())

    @patch('pt_backend.repositories.NewsRepository.get_all_news_name', side_effect=ObjectDoesNotExist)
    def test_get_filters_exception(self, mock_get_all_news_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"error": "No news found"})

    @patch('pt_backend.repositories.NewsRepository.get_all_news_name', side_effect=Exception("Database error"))
    def test_get_filters_exception(self, mock_get_all_news_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.json())