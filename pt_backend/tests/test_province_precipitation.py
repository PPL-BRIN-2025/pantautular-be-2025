from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from ..models import Climate
from ..repositories import ClimateRepository
from ..services import ClimateService, CacheService
import uuid
from unittest.mock import patch, MagicMock
import os
from .base_climate_test import BasePrecipitationRepositoryTest, BasePrecipitationServiceTest, BasePrecipitationViewTest
from ..views import ProvincePrecipitationView

class ClimateRepositoryTest(BasePrecipitationRepositoryTest):
    pass

class ClimateServiceTest(BasePrecipitationServiceTest):
    pass

class ProvincePrecipitationViewTest(BasePrecipitationViewTest):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.view = ProvincePrecipitationView()
        self.service = MagicMock()
        self.view.climate_service = self.service
        self.request = MagicMock()
        self.request.META = {'HTTP_X_API_KEY': 'test-api-key'}
        os.environ['SECRET_API_KEY'] = 'test-api-key'
        self.client.credentials(HTTP_X_API_KEY='test-api-key')

    def tearDown(self):
        super().tearDown()
        # Clean up environment variable
        os.environ.pop('SECRET_API_KEY', None)
        self.client.credentials()

    def test_unexpected_exception(self):
        """Test handling of unexpected exceptions"""
        self.service.get_province_precipitation.side_effect = Exception("Unexpected error")
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {"error": "Unexpected error"})

    def test_successful_response(self):
        """Test successful response with valid data"""
        mock_data = [
            {"province": "Aceh", "value": 100.0},
            {"province": "Bali", "value": 150.0}
        ]
        self.service.get_province_precipitation.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["id"], "ID-AC")
        self.assertEqual(response.data[0]["value"], 100.0)
        self.assertEqual(response.data[1]["id"], "ID-BA")
        self.assertEqual(response.data[1]["value"], 150.0)

    def test_serialization_error(self):
        mock_data = [{"invalid": "data"}]
        self.service.get_province_precipitation.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_invalid_precipitation_value(self):
        mock_data = [{"province": "Aceh", "value": "invalid"}]
        self.service.get_province_precipitation.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_invalid_province(self):
        """Test handling of invalid province name"""
        mock_data = [{"province": "InvalidProvince", "value": 80.0}]
        self.service.get_province_precipitation.return_value = {"error": "Invalid province name: InvalidProvince"}
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid province name: InvalidProvince"})

    def test_duplicate_provinces(self):
        """Test handling of duplicate province entries"""
        mock_data = [
            {"province": "Aceh", "value": 80.0},
            {"province": "Aceh", "value": 85.0}
        ]
        self.service.get_province_precipitation.return_value = {"error": "Duplicate province found: Aceh"}
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Duplicate province found: Aceh"})

    def test_missing_province(self):
        mock_data = [
            {"value": 100.0},  # Missing province
            {"province": "Bali", "value": 150.0}
        ]
        self.service.get_province_precipitation.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_missing_value(self):
        mock_data = [
            {"province": "Aceh"},  # Missing value
            {"province": "Bali", "value": 100.0}
        ]
        self.service.get_province_precipitation.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_serialization_error_with_invalid_value_type(self):
        mock_data = [
            {"province": "Aceh", "value": "invalid_value"},
            {"province": "Bali", "value": 150.0}
        ]
        self.service.get_province_precipitation.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_empty_data(self):
        self.service.get_province_precipitation.return_value = []
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "No precipitation data available."})

    def test_service_returns_error_dict(self):
        self.service.get_province_precipitation.return_value = {"error": "Some error occurred"}
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {"error": "Some error occurred"})

    # Positive Test Cases
    @patch('pt_backend.services.ClimateService.get_province_precipitation')
    def test_get_success_with_multiple_provinces(self, mock_get_precipitation):
        mock_get_precipitation.return_value = [
            {"province": "Aceh", "value": 100.0},  # Valid precipitation value
            {"province": "Bali", "value": 80.0}   # Valid precipitation value
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['id'], 'ID-AC')
        self.assertEqual(response.data[1]['id'], 'ID-BA')
        self.assertEqual(response.data[0]['value'], 100.0)
        self.assertEqual(response.data[1]['value'], 80.0)

    @patch('pt_backend.services.ClimateService.get_province_precipitation')
    def test_get_success_with_single_province(self, mock_get_precipitation):
        mock_get_precipitation.return_value = [
            {"province": "DKI Jakarta", "value": 150.0}  # Valid precipitation value
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], 'ID-JK')
        self.assertEqual(response.data[0]['value'], 150.0)

    # Negative Test Cases
    @patch('pt_backend.services.ClimateService.get_province_precipitation')
    def test_service_returns_error_dict(self, mock_get_precipitation):
        mock_get_precipitation.return_value = {"error": "Some error occurred"}
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"error": "Some error occurred"})

    @patch('pt_backend.services.ClimateService.get_province_precipitation')
    def test_extreme_precipitation_values(self, mock_get_precipitation):
        mock_get_precipitation.return_value = [
            {"province": "Aceh", "value": -10.0},  # Negative value
            {"province": "Bali", "value": 1500.0},  # Large value
            {"province": "DKI Jakarta", "value": 150.0}  # Normal value
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        self.assertEqual(response.data[0]['value'], -10.0)
        self.assertEqual(response.data[1]['value'], 1500.0)
        self.assertEqual(response.data[2]['value'], 150.0)
