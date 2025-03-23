from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from pt_backend.models import Case, Location, Disease, News
from pt_backend.services import CacheService
from unittest.mock import patch
from django.utils import timezone
from datetime import datetime
import uuid
import os
from unittest.mock import patch, Mock
import json

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

    @patch('pt_backend.services.CaseService.get_all_case_locations')
    def test_all_case_locations_get_exception(self, mock_get_locations):
        mock_get_locations.side_effect = Exception("Test exception")      
        url = reverse('all-case-locations')
        response = self.client.get(url)     
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"error": "An unexpected error occurred. Please try again later."})
    
    @patch('pt_backend.filter.service.CaseFilterService.filter_cases')
    def test_all_case_locations_post_exception(self, mock_filter_cases):
        mock_filter_cases.side_effect = Exception("Test exception")        
        url = reverse('all-case-locations')
        data = {"disease": "COVID-19"}
        response = self.client.post(url, data=json.dumps(data), content_type='application/json')        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"error": "An unexpected error occurred. Please try again later."})

    @patch('pt_backend.services.CaseService.get_all_case_locations')
    def test_all_case_locations_post_empty_data(self, mock_get_locations):
        mock_get_locations.return_value = []        
        url = reverse('all-case-locations')
        response = self.client.post(url, data=json.dumps({}), content_type='application/json')        
        mock_get_locations.assert_called_once()
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {"error": "No case locations found matching the filters"})
       
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
    
    @patch('pt_backend.repositories.DiseaseRepository.get_all_diseases_name')
    def test_filters_view_get_exception(self, mock_get_diseases):
        mock_get_diseases.side_effect = Exception("Test exception in filters")        
        url = reverse('filters')
        response = self.client.get(url)        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"error": "Test exception in filters"})
    
class PrevalenceViewTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('prevalence')
        
        # Create test data
        self.disease = Disease.objects.create(
            name="COVID-19", 
            level_of_alertness=5
        )
        self.location = Location.objects.create(
            latitude=-6.9175, 
            longitude=107.6191, 
            city="Bandung"
        )
        self.case = Case.objects.create(
            id=uuid.uuid4(),
            gender="Male",
            age=30,
            city="Bandung",
            status="active",
            disease=self.disease,
            location=self.location
        )
        self.news = News.objects.create(
            id=uuid.uuid4(), 
            portal="kompas.com", 
            type="health", 
            title="COVID-19 Case", 
            content="A new COVID-19 case detected...", 
            url="https://www.kompas.com/covid-case", 
            date_published=timezone.make_aware(datetime(2024, 1, 1)), 
            author="Dr. Smith", 
            case=self.case
        )
    
    # Positive Test Case
    def test_get_prevalence_success(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('year', response.data)
        self.assertIn('total_cases', response.data)
        self.assertIn('population', response.data)
        self.assertIn('prevalence', response.data)
        self.assertEqual(response.data['year'], 2024)
        self.assertEqual(response.data['total_cases'], 1)  
        self.assertEqual(response.data['population'], 281603800)  
        self.assertGreater(response.data['prevalence'], 0)
    
    # Negative Test Case
    @patch('pt_backend.repositories.CaseRepository.get_prevalence')
    def test_get_prevalence_with_repository_error(self, mock_get_prevalence):
        mock_get_prevalence.return_value = {"error": "Test error message"}
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Test error message")
    
    # Another Negative Test Case
    @patch('pt_backend.repositories.CaseRepository.get_prevalence')
    def test_get_prevalence_with_serializer_validation_error(self, mock_get_prevalence):
        mock_get_prevalence.return_value = {
            "year": "invalid",  
            "total_cases": 10,
            "population": 1000000,
            "prevalence": 0.001
        }
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('year', response.data)  
    
    # Corner Case 1: No cases in the database
    def test_get_prevalence_with_no_cases(self):
        News.objects.all().delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['year'], 2024)
        self.assertEqual(response.data['total_cases'], 0)
        self.assertEqual(response.data['prevalence'], 0.0)
    
    # Corner Case 2: ValueError exception handling
    @patch('pt_backend.repositories.CaseRepository.get_prevalence')
    def test_get_prevalence_with_value_error(self, mock_get_prevalence):
        mock_get_prevalence.side_effect = ValueError("Test ValueError")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Test ValueError") 
