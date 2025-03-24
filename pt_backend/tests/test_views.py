from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from pt_backend.models import Case, Location, Disease
from pt_backend.services import CacheService, CaseService, NewsService
from pt_backend.repositories import CaseRepository, NewsRepository
import uuid
import os
from unittest.mock import patch, Mock


class CaseAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_key = os.getenv("SECRET_API_KEY", "test-api-key")
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

        self.disease1 = Disease.objects.create(name="Flu", level_of_alertness=2)
        self.disease2 = Disease.objects.create(name="COVID-19", level_of_alertness=5)
        self.location1 = Location.objects.create(latitude=-6.2088, longitude=106.8456, city="Jakarta")
        self.location2 = Location.objects.create(latitude=-6.9175, longitude=107.6191, city="Bandung")
        self.case1 = Case.objects.create(
            id=uuid.uuid4(), gender="Male", age=30, city="Jakarta", status="confirmed", disease=self.disease1, location=self.location1
        )
        self.case2 = Case.objects.create(
            id=uuid.uuid4(), gender="Female", age=25, city="Bandung", status="recovered", disease=self.disease2, location=self.location2
        )

        self.cache_service = CacheService()

    def test_get_all_case_locations(self):
        response = self.client.get('/cases/locations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(len(response_data), 2)
        
        response_data.sort(key=lambda x: x['city'])
        expected_data = [
            {
                "id": str(self.case2.id),
                "location__longitude": "107.619100",
                "location__latitude": "-6.917500",
                "city": "Bandung"
            },
            {
                "id": str(self.case1.id),
                "location__longitude": "106.845600",
                "location__latitude": "-6.208800",
                "city": "Jakarta"
            }
        ]
        expected_data.sort(key=lambda x: x['city'])
        self.assertEqual(response_data, expected_data)

    def test_get_all_case_locations_empty(self):
        Case.objects.all().delete()
        self.cache_service.delete("all_case_locations")
        response = self.client.get('/cases/locations/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"error": "No case locations found"})

    @patch('pt_backend.services.CaseService.get_all_case_locations')
    def test_get_all_case_locations_exception(self, mock_get_all_locations):
        mock_get_all_locations.side_effect = Exception("Database error")
        response = self.client.get('/cases/locations/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {"error": "An unexpected error occurred. Please try again later."})

    def test_get_all_case_locations_missing_api_key(self):
        self.client.credentials()
        response = self.client.get('/cases/locations/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json(), {"detail": "Invalid API Key"})

    def test_get_all_case_locations_invalid_api_key(self):
        self.client.credentials(HTTP_X_API_KEY="wrong-api-key")
        response = self.client.get('/cases/locations/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json(), {"detail": "Invalid API Key"})


class CaseFilterPostTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_key = os.getenv("SECRET_API_KEY", "test-api-key")
        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        
        self.patcher = patch('pt_backend.views.CaseFilterService')
        self.mock_filter_service = self.patcher.start()
        self.mock_filter_instance = Mock()
        self.mock_filter_service.return_value = self.mock_filter_instance

        self.test_uuid1 = uuid.uuid4()
        self.test_uuid2 = uuid.uuid4()

    def tearDown(self):
        self.patcher.stop()

    def test_post_filter_success(self):
        mock_cases = [
            {'id': str(self.test_uuid1), 'location__longitude': '106.845600', 'location__latitude': '-6.208800', 'city': 'Jakarta'},
            {'id': str(self.test_uuid2), 'location__longitude': '107.619100', 'location__latitude': '-6.917500', 'city': 'Bandung'}
        ]
        self.mock_filter_instance.filter_cases.return_value = mock_cases

        filter_data = {
            'diseases': ['COVID-19'],
            'locations': ['Jakarta']
        }
        response = self.client.post('/cases/locations/', filter_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.mock_filter_instance.filter_cases.assert_called_once_with(filter_data)
        self.assertEqual(response.json(), mock_cases)

    def test_post_filter_no_results(self):
        self.mock_filter_instance.filter_cases.return_value = []
        response = self.client.post('/cases/locations/', {'diseases': ['Unknown']}, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"error": "No case locations found matching the filters"})



    def test_post_filter_missing_api_key(self):
        self.client.credentials()
        response = self.client.post('/cases/locations/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json(), {"detail": "Invalid API Key"})

    def test_post_filter_invalid_api_key(self):
        self.client.credentials(HTTP_X_API_KEY="wrong-api-key")
        response = self.client.post('/cases/locations/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json(), {"detail": "Invalid API Key"})

class GenderDistAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_key = os.getenv("SECRET_API_KEY", "test-api-key")
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

        self.cache_service = CacheService()
        self.repository = CaseRepository()
        self.service = CaseService(self.repository, self.cache_service)

        self.disease = Disease.objects.create(name="COVID-19", level_of_alertness=5)
        self.location = Location.objects.create(
            latitude=-6.9175, longitude=107.6191, city="Bandung"
        )
        Case.objects.create(gender='male', age=30, city='CityA', status='biasa', severity='insiden', disease=self.disease, location=self.location)
        Case.objects.create(gender='female', age=25, city='CityB', status='minimal', severity='mortalitas', disease=self.disease, location=self.location)
        Case.objects.create(gender='male', age=40, city='CityC', status='bahaya', severity='hospitalisasi', disease=self.disease, location=self.location)

    def test_get_gender_dist(self):
        response = self.client.get('/api/cases/gender-distribution/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'male': 2, 'female': 1})
    
    def test_get_gender_dist_if_invalid_gender(self):
        Case.objects.create(gender='BLABLA', age=30, city='CityA', status='biasa', severity='insiden', disease=self.disease, location=self.location)
        response = self.client.get('/api/cases/gender-distribution/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'male':2, 'female':1}) #buat cek klo ada yg ga valid masi return gender yg valid atau nggak

    @patch('pt_backend.services.CaseService.get_gender_dist')
    def test_get_gender_dist_exception(self, mock_get_gender_dist):
        mock_get_gender_dist.return_value = {
            'male': 2,
            'female': 1
        }

        response = self.client.get('/api/cases/gender-distribution/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {
            'male': 2,
            'female': 1
        })

    @patch('pt_backend.services.CaseService.get_gender_dist')
    def test_get_gender_dist_exception(self, mock_get_gender_dist):
        mock_get_gender_dist.side_effect = Exception("Database error")

        response = self.client.get('/api/cases/gender-distribution/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {"error": "An unexpected error occurred. Please try again later."})

class NewsAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_key = os.getenv("SECRET_API_KEY", "test-api-key")
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

        # Setup for API tests
        self.patcher = patch('pt_backend.views.NewsService')
        self.mock_service_class = self.patcher.start()
        self.mock_service_instance = Mock()
        self.mock_service_class.return_value = self.mock_service_instance

        # Setup for service tests
        self.mock_repository = Mock(spec=NewsRepository)
        self.service = NewsService(self.mock_repository)

    def tearDown(self):
        self.patcher.stop()

    # API Tests
    def test_get_healthcare_news_statistics_api(self):
        mock_data = [
            {'portal': 'detik.com', 'news_count': 1, 'disease_count': 1},
            {'portal': 'kompas.com', 'news_count': 1, 'disease_count': 1},
            {'portal': 'kemenkes.go.id', 'news_count': 1, 'disease_count': 1},
            {'portal': 'bps.go.id', 'news_count': 2, 'disease_count': 1},
            {'portal': 'bpjs.go.id', 'news_count': 1, 'disease_count': 1},
            {'portal': 'kemenhub.go.id', 'news_count': 1, 'disease_count': 1},
            {'portal': 'who.int', 'news_count': 1, 'disease_count': 1}
        ]
        self.mock_service_instance.get_healthcare_news_statistics.return_value = mock_data

        response = self.client.get('/api/healthcare-news/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), mock_data)
        self.mock_service_instance.get_healthcare_news_statistics.assert_called_once()
    
    def test_get_healthcare_news_statistics_empty_api(self):
        self.mock_service_instance.get_healthcare_news_statistics.return_value = []

        response = self.client.get('/api/healthcare-news/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    def test_get_healthcare_news_statistics_exception_api(self):
        self.mock_service_instance.get_healthcare_news_statistics.side_effect = Exception("Database error")

        response = self.client.get('/api/healthcare-news/statistics/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {"error": "Error retrieving news statistics"})

    # Service Tests
    def test_get_healthcare_news_statistics_service(self):
        expected_data = [
            {'portal': 'detik.com', 'news_count': 1, 'disease_count': 1},
            {'portal': 'kompas.com', 'news_count': 1, 'disease_count': 1}
        ]
        self.mock_repository.get_healthcare_news_statistics.return_value = expected_data
        
        result = self.service.get_healthcare_news_statistics()
        
        self.assertEqual(result, expected_data)
        self.mock_repository.get_healthcare_news_statistics.assert_called_once()