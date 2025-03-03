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
        self.disease1 = Disease.objects.create(
            id=uuid.uuid4(), name="COVID-19", level_of_alertness=5
        )
        self.disease2 = Disease.objects.create(
            id=uuid.uuid4(), name="Ebola", level_of_alertness=4
        )
        self.repository = DiseaseRepository()

    def test_get_all_diseases_name(self):
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
        self.disease = Disease.objects.create(name="COVID-19", level_of_alertness=5)
        self.location1 = Location.objects.create(
            latitude=-6.2088, longitude=106.8456, name="Jakarta"
        )
        self.location2 = Location.objects.create(
            latitude=-6.9175, longitude=107.6191, name="Bandung"
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
        self.disease1 = Disease.objects.create(id=uuid.uuid4(), name="COVID-19", level_of_alertness=5)
        self.disease2 = Disease.objects.create(id=uuid.uuid4(), name="Ebola", level_of_alertness=4)

        self.location1 = Location.objects.create(id=uuid.uuid4(), latitude=-6.2088, longitude=106.8456, name="Jakarta")
        self.location2 = Location.objects.create(id=uuid.uuid4(), latitude=-6.9175, longitude=107.6191, name="Bandung")

        self.case1 = Case.objects.create(
            id=uuid.uuid4(),
            gender="Pria",
            age=30,
            city="Jakarta",
            status="kematian",
            disease=self.disease1,
            location=self.location1
        )
        self.case2 = Case.objects.create(
            id=uuid.uuid4(),
            gender="Wanita",
            age=25,
            city="Bandung",
            status="terjangkit",
            disease=self.disease2,
            location=self.location2
        )

        self.news1 = News.objects.create(
            id=uuid.uuid4(),
            portal="kompas.com",
            type="health",
            title="COVID-19 Detected in Jakarta",
            content="COVID-19 case detected in Jakarta...",
            url="https://www.kompas.com/covid-jakarta",
            author="Dr. Joko",
            case=self.case1
        )
        self.news2 = News.objects.create(
            id=uuid.uuid4(),
            portal="detik.com",
            type="health",
            title="SARS Detected in Medan",
            content="SARS case detected in Medan...",
            url="https://www.detik.com/sars-medan",
            author="Dr. Sari",
            case=self.case2
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
        self.diseaseRepository = DiseaseRepository()
        self.locationRepository = LocationRepository()
        self.newsRepository = NewsRepository()

        self.disease1 = Disease.objects.create(name="COVID-19", level_of_alertness=5)
        self.disease2 = Disease.objects.create(name="Ebola", level_of_alertness=4)

        self.location1 = Location.objects.create(id=uuid.uuid4(), latitude=-6.2088, longitude=106.8456, name="Jakarta")
        self.location2 = Location.objects.create(id=uuid.uuid4(), latitude=-6.9175, longitude=107.6191, name="Bandung")

        self.case1 = Case.objects.create(
            id=uuid.uuid4(),
            gender="Pria",
            age=30,
            city="Jakarta",
            status="kematian",
            disease=self.disease1,
            location=self.location1
        )
        self.case2 = Case.objects.create(
            id=uuid.uuid4(),
            gender="Wanita",
            age=25,
            city="Bandung",
            status="terjangkit",
            disease=self.disease2,
            location=self.location2
        )

        self.news1 = News.objects.create(
            id=uuid.uuid4(),
            portal="kompas.com",
            type="health",
            title="COVID-19 Detected in Jakarta",
            content="COVID-19 case detected in Jakarta...",
            url="https://www.kompas.com/covid-jakarta",
            author="Dr. Joko",
            case=self.case1
        )
        self.news2 = News.objects.create(
            id=uuid.uuid4(),
            portal="detik.com",
            type="health",
            title="SARS Detected in Medan",
            content="SARS case detected in Medan...",
            url="https://www.detik.com/sars-medan",
            author="Dr. Sari",
            case=self.case2
        )

    def test_get_filters(self):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {
            "diseases": ["COVID-19", "Ebola"],
            "locations": ["Jakarta", "Bandung"],
            "news": ["kompas.com", "detik.com"]
        })

class FilterAPITest(TestCase):
    def setUp(self):
        """Setup data sebelum test dijalankan"""
        self.client = APIClient()
        self.diseaseRepository = DiseaseRepository()
        self.locationRepository = LocationRepository()
        self.newsRepository = NewsRepository()

        self.disease1 = Disease.objects.create(id=uuid.uuid4(), name="COVID-19", level_of_alertness=5)
        self.disease2 = Disease.objects.create(id=uuid.uuid4(), name="Ebola", level_of_alertness=4)

        self.location1 = Location.objects.create(id=uuid.uuid4(), latitude=-6.2088, longitude=106.8456, name="Jakarta")
        self.location2 = Location.objects.create(id=uuid.uuid4(), latitude=-6.9175, longitude=107.6191, name="Bandung")

        self.case1 = Case.objects.create(
            id=uuid.uuid4(), gender="Pria", age=30, city="Jakarta", status="kematian", disease=self.disease1, location=self.location1
        )
        self.case2 = Case.objects.create(
            id=uuid.uuid4(), gender="Wanita", age=25, city="Bandung", status="terjangkit", disease=self.disease2, location=self.location2
        )

        #     portal, news_type , content , url ,author ,title ,release_date 
        self.news1 = News.objects.create(
            id=uuid.uuid4(), portal="kompas.com", type="health", title="COVID-19 Detected in Jakarta", content="COVID-19 case detected in Jakarta...", url="https://www.kompas.com/covid-jakarta", author="Dr. Joko", case=self.case1
        )
        self.news2 = News.objects.create(
            id=uuid.uuid4(), portal="detik.com", type="health", title="SARS Detected in Medan", content="SARS case detected in Medan...", url="https://www.detik.com/sars-medan", author="Dr. Sari", case=self.case2
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