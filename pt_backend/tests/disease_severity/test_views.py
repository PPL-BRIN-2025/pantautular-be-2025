from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from pt_backend.views import DiseaseSeverityStatsView
from unittest.mock import MagicMock, patch
from pt_backend.authentication import APIKeyAuthentication

class DiseaseSeverityStatsViewTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DiseaseSeverityStatsView.as_view()
        
    @patch('pt_backend.views.DiseaseService')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
    def test_get_disease_severity_stats_success(self, mock_auth, mock_service_class):
        """Test successful retrieval of disease severity stats"""
        # Setup authentication bypass
        mock_auth.return_value = (None, None)
        
        # Setup mock service
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        
        # Setup mock service response
        mock_service_instance.get_disease_severity_stats.return_value = [
            {
                "name": "Test Disease 1",
                "severity_counts": {
                    "hospitalisasi": 1,
                    "insiden": 2,
                    "mortalitas": 3
                },
                "total_cases": 6
            },
            {
                "name": "Test Disease 2",
                "severity_counts": {
                    "hospitalisasi": 4,
                    "insiden": 5,
                    "mortalitas": 6
                },
                "total_cases": 15
            }
        ]
        
        # Make request
        request = self.factory.get('/api/diseases/severity-stats/')
        response = self.view(request)
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 2)
        
        disease1 = response.data['data'][0]
        self.assertEqual(disease1['name'], "Test Disease 1")
        self.assertEqual(disease1['total_cases'], 6)
        self.assertEqual(disease1['severity_counts']['hospitalisasi'], 1)
        self.assertEqual(disease1['severity_counts']['insiden'], 2)
        self.assertEqual(disease1['severity_counts']['mortalitas'], 3)
        
    @patch('pt_backend.views.DiseaseService')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
    def test_get_disease_severity_stats_error(self, mock_auth, mock_service_class):
        """Test error handling in view when service returns error"""
        # Setup authentication bypass
        mock_auth.return_value = (None, None)
        
        # Setup mock service
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        
        # Setup mock service to return an error dict
        mock_service_instance.get_disease_severity_stats.return_value = {
            "error": "Test error message"
        }
        
        # Make request
        request = self.factory.get('/api/diseases/severity-stats/')
        response = self.view(request)
        
        # Verify error response
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "Test error message")
        
    @patch('pt_backend.views.DiseaseService')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
    def test_get_disease_severity_stats_exception(self, mock_auth, mock_service_class):
        """Test exception handling in view when service raises exception"""
        # Setup authentication bypass
        mock_auth.return_value = (None, None)
        
        # Setup mock service
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        
        # Setup mock service to raise exception
        mock_service_instance.get_disease_severity_stats.side_effect = Exception("Test exception")
        
        # Make request
        request = self.factory.get('/api/diseases/severity-stats/')
        response = self.view(request)
        
        # Verify error response
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], "An unexpected error occurred. Please try again later.")