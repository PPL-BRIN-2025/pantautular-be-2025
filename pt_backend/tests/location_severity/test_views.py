from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from pt_backend.views import LocationSeverityStatsView, CitySeverityStatsView
from unittest.mock import MagicMock, patch
from pt_backend.authentication import APIKeyAuthentication

class LocationSeverityStatsViewTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = LocationSeverityStatsView.as_view()
        
    @patch('pt_backend.views.LocationService')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
    def test_get_province_stats_success(self, mock_auth, mock_service_class):
        """Test successful retrieval of province severity stats"""
        # Setup authentication bypass
        mock_auth.return_value = (None, None)
        
        # Setup mock service
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        
        # Setup mock service response
        mock_service_instance.get_province_severity_stats.return_value = [
            {
                "name": "DKI Jakarta",
                "severity_counts": {
                    "hospitalisasi": 10,
                    "insiden": 5,
                    "mortalitas": 2
                },
                "total_cases": 17
            },
            {
                "name": "Jawa Barat",
                "severity_counts": {
                    "hospitalisasi": 8,
                    "insiden": 3,
                    "mortalitas": 1
                },
                "total_cases": 12
            }
        ]
        
        # Make request (province only now)
        request = self.factory.get('/api/locations/province/severity-stats/')
        response = self.view(request)
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 2)
        
        province1 = response.data['data'][0]
        self.assertEqual(province1['name'], "DKI Jakarta")
        self.assertEqual(province1['total_cases'], 17)
        self.assertEqual(province1['severity_counts']['hospitalisasi'], 10)
        self.assertEqual(province1['severity_counts']['insiden'], 5)
        self.assertEqual(province1['severity_counts']['mortalitas'], 2)
        
        # Verify service was called without parameters
        mock_service_instance.get_province_severity_stats.assert_called_once_with()
    
    @patch('pt_backend.views.LocationService')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
    def test_service_error(self, mock_auth, mock_service_class):
        """Test handling of service error"""
        # Setup authentication bypass
        mock_auth.return_value = (None, None)
        
        # Setup mock service to return error
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        mock_service_instance.get_province_severity_stats.return_value = {
            "error": "Test service error"
        }
        
        # Make request
        request = self.factory.get('/api/locations/province/severity-stats/')
        response = self.view(request)
        
        # Verify error response
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Test service error")
    
    @patch('pt_backend.views.LocationService')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
    def test_unexpected_exception(self, mock_auth, mock_service_class):
        """Test handling of unexpected exception"""
        # Setup authentication bypass
        mock_auth.return_value = (None, None)
        
        # Setup mock service to raise exception
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        mock_service_instance.get_province_severity_stats.side_effect = Exception("Unexpected test error")
        
        # Make request
        request = self.factory.get('/api/locations/province/severity-stats/')
        response = self.view(request)
        
        # Verify error response
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "An unexpected error occurred. Please try again later.")

class CitySeverityStatsViewTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CitySeverityStatsView.as_view()
        
    @patch('pt_backend.views.LocationService')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
    def test_get_city_stats_success(self, mock_auth, mock_service_class):
        """Test successful retrieval of city severity stats"""
        # Setup authentication bypass
        mock_auth.return_value = (None, None)
        
        # Setup mock service
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        
        # Setup mock service response
        mock_service_instance.get_city_severity_stats.return_value = [
            {
                "name": "Jakarta",
                "severity_counts": {
                    "hospitalisasi": 15,
                    "insiden": 8,
                    "mortalitas": 3
                },
                "total_cases": 26
            },
            {
                "name": "Bandung",
                "severity_counts": {
                    "hospitalisasi": 10,
                    "insiden": 4,
                    "mortalitas": 1
                },
                "total_cases": 15
            }
        ]
        
        # Make request
        request = self.factory.get('/api/locations/city/severity-stats/')
        response = self.view(request)
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 2)
        
        city1 = response.data['data'][0]
        self.assertEqual(city1['name'], "Jakarta")
        self.assertEqual(city1['total_cases'], 26)
        self.assertEqual(city1['severity_counts']['hospitalisasi'], 15)
        self.assertEqual(city1['severity_counts']['insiden'], 8)
        self.assertEqual(city1['severity_counts']['mortalitas'], 3)
        
        # Verify service was called
        mock_service_instance.get_city_severity_stats.assert_called_once_with()
    
    @patch('pt_backend.views.LocationService')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
    def test_service_error(self, mock_auth, mock_service_class):
        """Test handling of service error"""
        # Setup authentication bypass
        mock_auth.return_value = (None, None)
        
        # Setup mock service to return error
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        mock_service_instance.get_city_severity_stats.return_value = {
            "error": "Test service error"
        }
        
        # Make request
        request = self.factory.get('/api/locations/city/severity-stats/')
        response = self.view(request)
        
        # Verify error response
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Test service error")
    
    @patch('pt_backend.views.LocationService')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
    def test_unexpected_exception(self, mock_auth, mock_service_class):
        """Test handling of unexpected exception"""
        # Setup authentication bypass
        mock_auth.return_value = (None, None)
        
        # Setup mock service to raise exception
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        mock_service_instance.get_city_severity_stats.side_effect = Exception("Unexpected test error")
        
        # Make request
        request = self.factory.get('/api/locations/city/severity-stats/')
        response = self.view(request)
        
        # Verify error response
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "An unexpected error occurred. Please try again later.")