from datetime import datetime
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from pantau_tular.settings import CACHES
from pt_backend.models import Case, Location, Disease, News
from pt_backend.services import CacheService
from unittest.mock import patch
from django.utils import timezone
from datetime import datetime, timedelta
import uuid
import os
from unittest.mock import patch, Mock
import json
from ..views import StatisticsView

class CaseAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_key = os.getenv("SECRET_API_KEY", "test-api-key")
        self.client.credentials(HTTP_X_API_KEY=self.api_key)

        self.disease1 = Disease.objects.create(name="Flu", level_of_alertness=2)
        self.disease2 = Disease.objects.create(name="COVID-19", level_of_alertness=5)
        self.location1 = Location.objects.create(latitude=-6.2088, longitude=106.8456, city="Jakarta", province="DKI Jakarta")
        self.location2 = Location.objects.create(latitude=-6.9175, longitude=107.6191, city="Bandung", province="Jawa Barat")
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
                "city": "Bandung",
                "location__province": "Jawa Barat"
            },
            {
                "id": str(self.case1.id),
                "location__longitude": "106.845600",
                "location__latitude": "-6.208800",
                "city": "Jakarta",
                "location__province": "DKI Jakarta"
            }
        ]
        expected_data.sort(key=lambda x: x['city'])
        self.assertEqual(response_data, expected_data)

    def test_get_all_case_locations_empty(self):
        Case.objects.all().delete()
        response = self.client.get('/cases/locations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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
        self.assertEqual(response.data, {"error": "An unexpected error occurred. Please try again later."})
       
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
            {'id': str(self.test_uuid1), 'location__longitude': '106.845600', 'location__latitude': '-6.208800', 'city': 'Jakarta', 'location__province': 'DKI Jakarta'},
            {'id': str(self.test_uuid2), 'location__longitude': '107.619100', 'location__latitude': '-6.917500', 'city': 'Bandung', 'location__province': 'Jawa Barat'}
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
        self.assertEqual(response.json(), {"error": "An unexpected error occurred. Please try again later."})

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
    
class StatisticsViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_key = os.getenv("SECRET_API_KEY", "test-api-key")
        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        self.url = reverse('statistics')
        
        # Mock the APIKeyAuthentication to always authenticate successfully
        self.auth_patcher = patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
        self.mock_auth = self.auth_patcher.start()
        self.mock_auth.return_value = (None, None)  # Return (user, auth) tuple
        
        # Mock the StatisticsCoordinator
        self.coordinator_patcher = patch('pt_backend.views.StatisticsCoordinator')
        self.mock_coordinator = self.coordinator_patcher.start()
        
        # Create a mock instance for the coordinator
        self.mock_coordinator_instance = Mock()
        self.mock_coordinator.return_value = self.mock_coordinator_instance
        
        # Setup the mock to return a specific value
        self.mock_coordinator_instance.generate_comprehensive_report.return_value = {
            "prevalence_statistics": {
                "year": 2023,
                "total_cases": 100,
                "population": 278696200,
                "prevalence": 0.0359
            }
        }
        
    def tearDown(self):
        self.coordinator_patcher.stop()
        self.auth_patcher.stop()
        
    def test_statistics_get(self):
        """Test retrieving statistics with GET method (no filters)"""
        response = self.client.get(self.url)
        
        # Check that the response is successful
        self.assertEqual(response.status_code, 200)
        
        # Verify that generate_comprehensive_report was called without filter_params
        self.mock_coordinator_instance.generate_comprehensive_report.assert_called_once_with()
        
        # Verify the response contains the expected data
        self.assertIn("prevalence_statistics", response.data)
        self.assertEqual(response.data["prevalence_statistics"]["year"], 2023)
        
    def test_statistics_get_with_exception(self):
        """Test handling of exceptions in GET method"""
        # Mock the coordinator to raise an exception
        self.mock_coordinator_instance.generate_comprehensive_report.side_effect = Exception("Test error")
        
        response = self.client.get(self.url)
        
        # Check error response
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {"error": "An error occurred while fetching statistics"})
        
    def test_statistics_with_start_date(self):
        """Test that start_date is correctly passed to the statistics coordinator"""
        # Make the request with a start_date
        response = self.client.post(
            self.url,
            data=json.dumps({"start_date": "2023-01-01"}),
            content_type='application/json'
        )
        
        # Check that the response is successful
        self.assertEqual(response.status_code, 200)
        
        # Verify that generate_comprehensive_report was called with the correct filter_params
        self.mock_coordinator_instance.generate_comprehensive_report.assert_called_once()
        call_args = self.mock_coordinator_instance.generate_comprehensive_report.call_args[1]
        
        # Check that the date_range parameter was correctly set
        self.assertIn('date_range', call_args)
        self.assertEqual(call_args['date_range']['start'], "2023-01-01")
        self.assertIsNone(call_args['date_range']['end'])
        
        # Verify the response contains the expected data
        self.assertIn("prevalence_statistics", response.data)
        self.assertEqual(response.data["prevalence_statistics"]["year"], 2023)
        
    def test_statistics_without_start_date(self):
        """Test that the default behavior is used when no start_date is provided"""
        # Make the request without a start_date
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type='application/json'
        )
        
        # Check that the response is successful
        self.assertEqual(response.status_code, 200)
        
        # Verify that generate_comprehensive_report was called
        self.mock_coordinator_instance.generate_comprehensive_report.assert_called_once()
        
        # Verify the response contains the expected data
        self.assertIn("prevalence_statistics", response.data)
        self.assertEqual(response.data["prevalence_statistics"]["year"], 2023)
        
    def test_statistics_with_date_range(self):
        """Test that both start_date and end_date are correctly passed to the statistics coordinator"""
        # Make the request with both start_date and end_date
        response = self.client.post(
            self.url,
            data=json.dumps({
                "start_date": "2023-01-01",
                "end_date": "2023-12-31"
            }),
            content_type='application/json'
        )
        
        # Check that the response is successful
        self.assertEqual(response.status_code, 200)
        
        # Verify that generate_comprehensive_report was called with the correct filter_params
        self.mock_coordinator_instance.generate_comprehensive_report.assert_called_once()
        call_args = self.mock_coordinator_instance.generate_comprehensive_report.call_args[1]
        
        # Check that the date_range parameter was correctly set
        self.assertIn('date_range', call_args)
        self.assertEqual(call_args['date_range']['start'], "2023-01-01")
        self.assertEqual(call_args['date_range']['end'], "2023-12-31")
        
        # Verify the response contains the expected data
        self.assertIn("prevalence_statistics", response.data)
        self.assertEqual(response.data["prevalence_statistics"]["year"], 2023)
    
    def test_statistics_with_disease_filter(self):
        """Test filtering statistics by disease"""
        response = self.client.post(
            self.url,
            data=json.dumps({"diseases": ["COVID-19", "Dengue"]}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify generate_comprehensive_report was called with disease filter
        call_args = self.mock_coordinator_instance.generate_comprehensive_report.call_args[1]
        self.assertIn('disease', call_args)
        self.assertEqual(call_args['disease'], ["COVID-19", "Dengue"])
    
    def test_statistics_with_location_filter(self):
        """Test filtering statistics by location"""
        response = self.client.post(
            self.url,
            data=json.dumps({"locations": ["Jakarta", "Bandung"]}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify generate_comprehensive_report was called with cities filter
        call_args = self.mock_coordinator_instance.generate_comprehensive_report.call_args[1]
        self.assertIn('cities', call_args)
        self.assertEqual(call_args['cities'], ["Jakarta", "Bandung"])
    
    def test_statistics_with_portal_filter(self):
        """Test filtering statistics by portal"""
        response = self.client.post(
            self.url,
            data=json.dumps({"portals": ["kompas.com", "detik.com"]}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify generate_comprehensive_report was called with portals filter
        call_args = self.mock_coordinator_instance.generate_comprehensive_report.call_args[1]
        self.assertIn('portals', call_args)
        self.assertEqual(call_args['portals'], ["kompas.com", "detik.com"])
    
    def test_statistics_with_alertness_filter(self):
        """Test filtering statistics by alertness level"""
        response = self.client.post(
            self.url,
            data=json.dumps({"level_of_alertness": 3}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify generate_comprehensive_report was called with disease_alertness filter
        call_args = self.mock_coordinator_instance.generate_comprehensive_report.call_args[1]
        self.assertIn('disease_alertness', call_args)
        self.assertEqual(call_args['disease_alertness'], 3)
    
    def test_statistics_with_zero_alertness_level(self):
        """Test that alertness level of 0 doesn't get passed as a filter"""
        response = self.client.post(
            self.url,
            data=json.dumps({"level_of_alertness": 0}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify disease_alertness wasn't included in filter params
        call_args = self.mock_coordinator_instance.generate_comprehensive_report.call_args[1]
        self.assertNotIn('disease_alertness', call_args)
    
    def test_statistics_with_combined_filters(self):
        """Test using multiple filters together"""
        response = self.client.post(
            self.url,
            data=json.dumps({
                "diseases": ["COVID-19"],
                "locations": ["Jakarta"],
                "portals": ["kompas.com"],
                "level_of_alertness": 2,
                "start_date": "2023-01-01",
                "end_date": "2023-06-30"
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify all filters were correctly passed
        call_args = self.mock_coordinator_instance.generate_comprehensive_report.call_args[1]
        self.assertEqual(call_args['disease'], ["COVID-19"])
        self.assertEqual(call_args['cities'], ["Jakarta"])
        self.assertEqual(call_args['portals'], ["kompas.com"])
        self.assertEqual(call_args['disease_alertness'], 2)
        self.assertEqual(call_args['date_range']['start'], "2023-01-01")
        self.assertEqual(call_args['date_range']['end'], "2023-06-30")
    
    def test_statistics_post_with_exception(self):
        """Test handling of exceptions in POST method"""
        # Mock the coordinator to raise an exception
        self.mock_coordinator_instance.generate_comprehensive_report.side_effect = Exception("Test error")
        
        response = self.client.post(
            self.url,
            data=json.dumps({"diseases": ["COVID-19"]}),
            content_type='application/json'
        )
        
        # Check error response
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {"error": "An error occurred while fetching statistics"})
    
    def test_statistics_missing_api_key(self):
        """Test that requests without API key are rejected"""
        # Stop the authentication mock to test real authentication
        self.auth_patcher.stop()
        
        # Remove API key from request
        self.client.credentials()
        
        # Try both GET and POST
        get_response = self.client.get(self.url)
        post_response = self.client.post(
            self.url, 
            data=json.dumps({"diseases": ["COVID-19"]}),
            content_type='application/json'
        )
        
        # Restart the auth patcher for other tests
        self.auth_patcher = patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
        self.mock_auth = self.auth_patcher.start()
        self.mock_auth.return_value = (None, None)
        
        # Both should be forbidden
        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
    
    def test_statistics_invalid_api_key(self):
        """Test that requests with invalid API key are rejected"""
        # Stop the authentication mock to test real authentication
        self.auth_patcher.stop()
        
        # Set invalid API key
        self.client.credentials(HTTP_X_API_KEY="invalid-key")
        
        # Try both GET and POST
        get_response = self.client.get(self.url)
        post_response = self.client.post(
            self.url, 
            data=json.dumps({"diseases": ["COVID-19"]}),
            content_type='application/json'
        )
        
        # Restart the auth patcher for other tests
        self.auth_patcher = patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
        self.mock_auth = self.auth_patcher.start()
        self.mock_auth.return_value = (None, None)
        
        # Both should be forbidden
        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
