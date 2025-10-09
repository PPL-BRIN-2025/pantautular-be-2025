from datetime import datetime
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from pantau_tular.settings import CACHES
from pt_backend.models import Case, Location, Disease, News, User
from pt_backend.services import CacheService
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import datetime, timedelta
import uuid
import os
from unittest.mock import patch, Mock
from rest_framework_simplejwt.tokens import RefreshToken
import json
from ..views import StatisticsView, SeverityFilteringStatsView

class CaseAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Set up API key authentication
        os.environ['SECRET_API_KEY'] = 'test-api-key'
        self.client.credentials(HTTP_X_API_KEY='test-api-key')

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

    def tearDown(self):
        # Clean up environment variable
        os.environ.pop('SECRET_API_KEY', None)

    def test_get_all_case_locations(self):
        """Test getting all case locations successfully"""
        mock_locations = [
            {"id": str(self.case1.id), "location__longitude": '106.845600', "location__latitude": '-6.208800', "city": "Jakarta", "location__province": "DKI Jakarta"},
            {"id": str(self.case2.id), "location__longitude": '107.619100', "location__latitude": '-6.917500', "city": "Bandung", "location__province": "Jawa Barat"}
        ]
        
        with patch('pt_backend.services.CaseService.get_all_case_locations') as mock_get_locations:
            mock_get_locations.return_value = mock_locations
            url = reverse('all-case-locations')
            response = self.client.get(url)
            response_data = [dict(x) for x in response.data]
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response_data, mock_locations)
            mock_get_locations.assert_called_once()

    def test_get_all_case_locations_empty(self):
        """Test getting all case locations when no data exists"""
        with patch('pt_backend.services.CaseService.get_all_case_locations') as mock_get_locations:
            mock_get_locations.return_value = []
            url = reverse('all-case-locations')
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(response.data, {"error": "No case locations found"})
            mock_get_locations.assert_called_once()

    def test_get_all_case_locations_exception(self):
        """Test handling exception when getting case locations"""
        with patch('pt_backend.services.CaseService.get_all_case_locations') as mock_get_locations:
            mock_get_locations.side_effect = Exception("Database error")
            url = reverse('all-case-locations')
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertIn('error', response.data)

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
    
    @patch('pt_backend.services.CaseService.get_all_case_locations')
    def test_all_case_locations_post_exception(self, mock_get_locations):
        mock_get_locations.side_effect = Exception("Test exception")
        url = reverse('all-case-locations')
        data = {"disease": "COVID-19"}
        response = self.client.post(url, data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('pt_backend.services.CaseService.get_all_case_locations')
    def test_all_case_locations_post_empty_data(self, mock_get_locations):
        mock_get_locations.return_value = []        
        url = reverse('all-case-locations')
        response = self.client.post(url, data=json.dumps({}), content_type='application/json')        
        mock_get_locations.assert_called_once()
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {"error": "No cases found with the given filters"})
       
class CaseFilterPostTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        os.environ['SECRET_API_KEY'] = 'test-api-key'
        self.client.credentials(HTTP_X_API_KEY='test-api-key')
        self.test_uuid1 = uuid.uuid4()
        self.test_uuid2 = uuid.uuid4()

    def tearDown(self):
        os.environ.pop('SECRET_API_KEY', None)

    def test_post_filter_success(self):
        """Test successful POST request with filters"""
        mock_filtered_cases = [
            {"id": str(self.test_uuid1), "location__longitude": '106.845600', "location__latitude": '-6.208800', "city": "Jakarta", "location__province": "DKI Jakarta"},
            {"id": str(self.test_uuid2), "location__longitude": '107.619100', "location__latitude": '-6.917500', "city": "Bandung", "location__province": "Jawa Barat"}
        ]
        with patch('pt_backend.filter.service.CaseFilterService.filter_cases') as mock_filter:
            mock_filter.return_value = mock_filtered_cases
            url = reverse('all-case-locations')
            data = {"provinces": ["DKI Jakarta", "Jawa Barat"]}
            response = self.client.post(url, data, format='json')
            response_data = [dict(x) for x in response.data]
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response_data, mock_filtered_cases)
            mock_filter.assert_called_once_with(data)

    def test_post_filter_no_results(self):
        """Test POST request with filters that return no results"""
        with patch('pt_backend.filter.service.CaseFilterService.filter_cases') as mock_filter:
            mock_filter.return_value = []
            url = reverse('all-case-locations')
            data = {"provinces": ["NonExistentProvince"]}
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(response.data, {"error": "No cases found with the given filters"})
            mock_filter.assert_called_once_with(data)

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
            data=json.dumps({
                "locations": {
                    "cities": ["Jakarta", "Bandung"]
                }
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)

        call_args = self.mock_coordinator_instance.generate_comprehensive_report.call_args[1]
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
                "locations": {"cities": ["Jakarta"]},
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

class WeightedSeverityAnalysisViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_key = os.getenv("SECRET_API_KEY", "test-api-key")
        self.user = User.objects.create(
            name="Weighted Tester",
            email="weighted@example.com",
            password="test-password",
            role="ADMIN",
        )
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self._set_credentials()
        self.url = reverse('province-weighted-severity')
        
        # Mock the APIKeyAuthentication to always authenticate successfully
        self.auth_patcher = patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
        self.mock_auth = self.auth_patcher.start()
        self.mock_auth.return_value = (None, None)
        
        # Mock the CaseService and AverageSeverityByProvince
        self.case_service_patcher = patch('pt_backend.views.CaseService')
        self.mock_case_service = self.case_service_patcher.start()
        self.mock_case_service_instance = Mock()
        self.mock_case_service.return_value = self.mock_case_service_instance
        
        self.severity_analyzer_patcher = patch('pt_backend.views.AverageSeverityByProvince')
        self.mock_severity_analyzer = self.severity_analyzer_patcher.start()
        self.mock_severity_analyzer_instance = Mock()
        self.mock_severity_analyzer.return_value = self.mock_severity_analyzer_instance
        
    def tearDown(self):
        self.auth_patcher.stop()
        DownloadEvent.objects.all().delete()
        self.case_service_patcher.stop()
        self.severity_analyzer_patcher.stop()

    def _set_credentials(self, api_key=None):
        headers = {
            "HTTP_X_API_KEY": api_key or self.api_key,
            "HTTP_AUTHORIZATION": f"Bearer {self.access_token}",
        }
        self.client.credentials(**headers)
    
    def test_get_success(self):
        # Setup mock data
        mock_result = {
            "Jawa Barat": {
                "weighted_score": 2.5,
                "status": "biasa"
            },
            "Papua": {
                "weighted_score": 4.2,
                "status": "katastropik"
            }
        }
        self.mock_severity_analyzer_instance.compute.return_value = mock_result
        
        # Make request
        response = self.client.get(self.url)
        
        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, mock_result)
        
    def test_get_no_data(self):
        # Setup mock to return empty result
        self.mock_severity_analyzer_instance.compute.return_value = {}
        
        # Make request
        response = self.client.get(self.url)
        
        # Verify response
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data, {"error": "No case data available"})
        
    def test_get_with_exception(self):
        # Setup mock to raise exception
        self.mock_severity_analyzer_instance.compute.side_effect = Exception("Test error")
        
        # Make request
        response = self.client.get(self.url)
        
        # Verify error response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"error": "An unexpected error occurred. Please try again later."})
    
    def test_authentication_required(self):
        # Stop the authentication mock to test real authentication
        self.auth_patcher.stop()

        # Remove API key from request
        self.client.credentials()

        # Make request
        response = self.client.get(self.url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data, {"detail": "Invalid API Key"})

        # Restore patcher for future tests
        self.auth_patcher = patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
        self.mock_auth = self.auth_patcher.start()
        self.mock_auth.return_value = (None, None)

    def test_invalid_api_key(self):
        # Stop the authentication mock to test real authentication
        self.auth_patcher.stop()

        # Set invalid API key
        self._set_credentials(api_key="invalid-key")

        # Make request
        response = self.client.get(self.url)

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data, {"detail": "Invalid API Key"})

        # Restore patcher for future tests
        self.auth_patcher = patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
        self.mock_auth = self.auth_patcher.start()
        self.mock_auth.return_value = (None, None)

class SeverityFilteringStatsViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_key = os.getenv("SECRET_API_KEY", "test-api-key")
        self.client.credentials(HTTP_X_API_KEY=self.api_key)
        self.url = reverse('severity-filtering-stats')
        
        # Mock the APIKeyAuthentication to always authenticate successfully
        self.auth_patcher = patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
        self.mock_auth = self.auth_patcher.start()
        self.mock_auth.return_value = (None, None)  # Return (user, auth) tuple
        
        # Mock SeverityFilteringService
        self.service_patcher = patch('pt_backend.views.SeverityFilteringService')
        self.mock_service = self.service_patcher.start()
        self.mock_service_instance = Mock()
        self.mock_service.return_value = self.mock_service_instance
        
        # Mock CacheService
        self.cache_patcher = patch('pt_backend.views.CacheService')
        self.mock_cache = self.cache_patcher.start()
        self.mock_cache_instance = Mock()
        self.mock_cache.return_value = self.mock_cache_instance
        
        # Sample mock results
        self.mock_results = {
            "disease_stats": [{"name": "COVID-19", "severity_counts": {"hospitalisasi": 10, "insiden": 5, "mortalitas": 2}, "total_cases": 17}],
            "province_stats": [{"name": "DKI Jakarta", "severity_counts": {"hospitalisasi": 8, "insiden": 3, "mortalitas": 1}, "total_cases": 12}],
            "city_stats": [{"name": "Jakarta", "severity_counts": {"hospitalisasi": 6, "insiden": 2, "mortalitas": 1}, "total_cases": 9}]
        }
        
    def tearDown(self):
        self.auth_patcher.stop()
        self.service_patcher.stop()
        self.cache_patcher.stop()
        
    def test_get_method_not_allowed(self):
        """Test that GET method returns 405 Method Not Allowed"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def test_post_without_filters(self):
        """Test POST without any filters"""
        # Setup mock
        self.mock_cache_instance.get.return_value = None
        self.mock_service_instance.get_filter_stats.return_value = self.mock_results
        
        # Make request
        response = self.client.post(self.url, data={}, format='json')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,
            cities=None,
            news_portals=None,
            alert_levels=None,
            date_range=None
        )
        self.assertEqual(response.json(), self.mock_results)
        # Verify caching occurred
        self.mock_cache_instance.set.assert_called_once()
    
    def test_post_with_cached_results(self):
        """Test POST with cached results available"""
        # Setup cache hit
        self.mock_cache_instance.get.return_value = self.mock_results
        
        # Make request
        response = self.client.post(self.url, data={"diseases": ["COVID-19"]}, format='json')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), self.mock_results)
        # Verify service was not called (used cache instead)
        self.mock_service_instance.get_filter_stats.assert_not_called()
    
    def test_post_with_location_processing(self):
        """Test location data processing in POST request"""
        # Setup mocks
        self.mock_cache_instance.get.return_value = None
        self.mock_service_instance.get_filter_stats.return_value = self.mock_results
        
        # Mock Location.objects.filter
        with patch('pt_backend.views.Location.objects.filter') as mock_loc_filter:
            mock_exists = MagicMock()
            mock_exists.exists.return_value = True
            mock_loc_filter.return_value = mock_exists
            
            # Make request with location data
            response = self.client.post(
                self.url,
                data={
                    "locations": {
                        "provinces": ["DKI Jakarta", "Jawa Barat"],
                        "cities": ["Jakarta", "Bandung"]
                    }
                },
                format='json'
            )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        call_args = self.mock_service_instance.get_filter_stats.call_args[1]
    
        # Check each argument individually with flexible ordering where needed
        self.assertEqual(call_args['diseases'], None)
        self.assertIsNotNone(call_args['provinces'])
        self.assertCountEqual(call_args['provinces'], ["DKI Jakarta", "Jawa Barat"])
        self.assertIsNotNone(call_args['cities'])
        self.assertCountEqual(call_args['cities'], ["Jakarta", "Bandung"])
        self.assertEqual(call_args['news_portals'], None)
        self.assertEqual(call_args['alert_levels'], None)
        self.assertEqual(call_args['date_range'], None)
        self.mock_service_instance.get_filter_stats.assert_called_once()
        
    def test_post_with_invalid_location(self):
        """Test location data processing with invalid locations"""
        # Setup mocks
        self.mock_cache_instance.get.return_value = None
        self.mock_service_instance.get_filter_stats.return_value = self.mock_results
        
        # Mock Location.objects.filter for invalid province
        with patch('pt_backend.views.Location.objects.filter') as mock_loc_filter:
            mock_exists = MagicMock()
            mock_exists.exists.return_value = False  # Location does not exist
            mock_loc_filter.return_value = mock_exists
            
            # Make request with invalid location data
            response = self.client.post(
                self.url,
                data={
                    "locations": {
                        "provinces": ["Invalid Province"],
                        "cities": ["Invalid City"]
                    }
                },
                format='json'
            )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,  # Should be None since province doesn't exist
            cities=None,     # Should be None since city doesn't exist
            news_portals=None,
            alert_levels=None,
            date_range=None
        )
    
    def test_post_with_date_range(self):
        """Test POST with date range"""
        # Setup mocks
        self.mock_cache_instance.get.return_value = None
        self.mock_service_instance.get_filter_stats.return_value = self.mock_results
        
        # Make request with date range
        response = self.client.post(
            self.url,
            data={
                "start_date": "2023-01-01",
                "end_date": "2023-12-31"
            },
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,
            cities=None,
            news_portals=None,
            alert_levels=None,
            date_range=("2023-01-01", "2023-12-31")
        )
    
    def test_post_with_portals_and_alertness(self):
        """Test POST with news portals and alertness level"""
        # Setup mocks
        self.mock_cache_instance.get.return_value = None
        self.mock_service_instance.get_filter_stats.return_value = self.mock_results
        
        # Make request with portals and alertness
        response = self.client.post(
            self.url,
            data={
                "portals": ["Kompas", "Detik"],
                "level_of_alertness": "3"
            },
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,
            cities=None,
            news_portals=["Kompas", "Detik"],
            alert_levels=3,
            date_range=None
        )
    
    def test_post_with_invalid_alertness_level(self):
        """Test POST with invalid alertness level"""
        # Setup mocks
        self.mock_cache_instance.get.return_value = None
        
        # Make request with invalid alertness level
        response = self.client.post(
            self.url,
            data={
                "level_of_alertness": "not_a_number"
            },
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("invalid literal for int()", response.data["error"])
        # Service should not be called with invalid input
        self.mock_service_instance.get_filter_stats.assert_not_called()
    
    def test_post_with_cache_generation_error(self):
        """Test handling of cache key generation error"""
        # Setup mocks
        self.mock_cache_instance.get.return_value = None
        self.mock_service_instance.get_filter_stats.return_value = self.mock_results
        
        # Force error in cache key generation
        with patch('pt_backend.views.SeverityFilteringStatsView._generate_cache_key') as mock_gen_key:
            mock_gen_key.side_effect = Exception("Cache key error")
            
            # Make request
            response = self.client.post(self.url, data={"diseases": ["COVID-19"]}, format='json')
        
        # The view returns 400 Bad Request when cache generation fails, not 200 OK
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Service should NOT be called when there's a cache key generation error
        self.mock_service_instance.get_filter_stats.assert_not_called()
        
        # Check error message
        self.assertIn("error", response.data)
        self.assertIn("Cache key error", response.data["error"])

    def test_post_with_service_exception(self):
        """Test handling exception from service"""
        # Setup mocks
        self.mock_cache_instance.get.return_value = None
        self.mock_service_instance.get_filter_stats.side_effect = Exception("Service error")
        
        # Make request
        response = self.client.post(self.url, data={"diseases": ["COVID-19"]}, format='json')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Service error", response.data["error"])
    
    def test_missing_api_key(self):
        """Test request without API key"""
        # Stop auth mock to test actual authentication
        self.auth_patcher.stop()
        
        # Remove API key from request
        self.client.credentials()
        
        # Make request
        response = self.client.post(self.url, data={}, format='json')
        
        # Restart auth mock for other tests
        self.auth_patcher = patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
        self.mock_auth = self.auth_patcher.start()
        self.mock_auth.return_value = (None, None)
        
        # Assertion
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data, {"detail": "Invalid API Key"})
    
    def test_invalid_api_key(self):
        """Test request with invalid API key"""
        # Stop auth mock to test actual authentication
        self.auth_patcher.stop()
        
        # Set invalid API key
        self.client.credentials(HTTP_X_API_KEY="invalid-key")
        
        # Make request
        response = self.client.post(self.url, data={}, format='json')
        
        # Restart auth mock for other tests
        self.auth_patcher = patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
        self.mock_auth = self.auth_patcher.start()
        self.mock_auth.return_value = (None, None)
        
        # Assertion
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data, {"detail": "Invalid API Key"})
    
    def test_generate_cache_key(self):
        """Test the cache key generation function"""
        view = SeverityFilteringStatsView()
        view.cache_service = self.mock_cache_instance
        
        # Test with simple parameters
        filter_params = {
            'diseases': ['COVID-19'],
            'provinces': ['DKI Jakarta'],
            'cities': None,
            'news_portals': None,
            'alert_levels': 3,
            'date_range': ('2023-01-01', '2023-12-31')
        }
        
        # Mock cache get to return None and then execute
        self.mock_cache_instance.get.return_value = None
        
        # Execute the function
        view._generate_cache_key(filter_params)
        
        # Verify cache get was called
        self.mock_cache_instance.get.assert_called_once()
        
        # Test with nested parameters that require conversion
        filter_params = {
            'diseases': ['COVID-19', 'Dengue'],
            'provinces': {'DKI Jakarta', 'Jawa Barat'},  # Using a set
            'cities': ['Jakarta', 'Bandung'],
            'news_portals': ['Kompas'],
            'alert_levels': 3,
            'date_range': {'start': '2023-01-01', 'end': '2023-12-31'}  # Using a dict
        }
        
        # Execute again with complex parameters
        self.mock_cache_instance.get.reset_mock()
        self.mock_cache_instance.get.return_value = None
        view._generate_cache_key(filter_params)
    
    def test_generate_cache_key_with_cached_result(self):
        """Test when cache key generation returns cached result"""
        view = SeverityFilteringStatsView()
        view.cache_service = self.mock_cache_instance
        
        # Setup mock to return cached result
        self.mock_cache_instance.get.return_value = self.mock_results
        
        # Execute the function
        result = view._generate_cache_key({'diseases': ['COVID-19']})
        
        # Verify result is the cached result
        self.assertEqual(result, self.mock_results)
        self.mock_cache_instance.get.assert_called_once()
    
    def test_process_location_data_with_empty_input(self):
        """Test _process_location_data with empty input"""
        view = SeverityFilteringStatsView()
        
        # Test with empty input
        provinces, cities = view._process_location_data({})
        self.assertIsNone(provinces)
        self.assertIsNone(cities)
        
        # Test with None input
        provinces, cities = view._process_location_data(None)
        self.assertIsNone(provinces)
        self.assertIsNone(cities)
        
    def test_process_location_data_with_location_list(self):
        """Test _process_location_data with a list of locations"""
        view = SeverityFilteringStatsView()
        
        # Mock Location.objects.filter
        with patch('pt_backend.views.Location.objects.filter') as mock_loc_filter:
            mock_exists = MagicMock()
            mock_exists.exists.return_value = True
            mock_loc_filter.return_value = mock_exists
            
            # Call the method with valid input
            provinces, cities = view._process_location_data({
                'provinces': ['DKI Jakarta', 'DKI Jakarta', 'Jawa Barat'],  # Duplicate intentional
                'cities': ['Jakarta', 'Bandung']
            })
            
        # Check that duplicates are removed and values are processed correctly
        self.assertEqual(len(provinces), 2)
        self.assertIn('DKI Jakarta', provinces)
        self.assertIn('Jawa Barat', provinces)
        self.assertEqual(len(cities), 2)
        self.assertIn('Jakarta', cities)
        self.assertIn('Bandung', cities)
