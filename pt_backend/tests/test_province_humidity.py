from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from ..views import ProvinceHumidityView
from ..services import ClimateService
from unittest.mock import patch, MagicMock
import os
from .base_climate_test import BaseHumidityRepositoryTest, BaseHumidityServiceTest, BaseHumidityViewTest

class ClimateRepositoryTest(BaseHumidityRepositoryTest):
    pass

class ClimateServiceTest(BaseHumidityServiceTest):
    pass

class ProvinceHumidityViewTest(BaseHumidityViewTest):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.view = ProvinceHumidityView()
        self.service = MagicMock()
        self.view.climate_service = self.service
        self.request = MagicMock()
        self.request.META = {
            'HTTP_X_API_KEY': 'test-api-key',
            'HTTP_AUTHORIZATION': f'Bearer {self.access_token}',
        }
        os.environ['SECRET_API_KEY'] = 'test-api-key'
        self._set_credentials()

    def tearDown(self):
        super().tearDown()
        # Clean up environment variable
        os.environ.pop('SECRET_API_KEY', None)
        self.client.credentials()

    def test_unexpected_exception(self):
        """Test handling of unexpected exceptions"""
        self.service.get_province_humidity.side_effect = Exception("Unexpected error")
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {"error": "Unexpected error"})

    def test_successful_response(self):
        """Test successful response with valid data"""
        mock_data = [
            {"province": "Aceh", "value": 80.0},
            {"province": "Bali", "value": 85.0}
        ]
        self.service.get_province_humidity.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["id"], "ID-AC")
        self.assertEqual(response.data[0]["value"], 80.0)
        self.assertEqual(response.data[1]["id"], "ID-BA")
        self.assertEqual(response.data[1]["value"], 85.0)

    def test_serialization_error(self):
        mock_data = [{"invalid": "data"}]
        self.service.get_province_humidity.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_invalid_humidity_value(self):
        mock_data = [{"province": "Aceh", "value": "invalid"}]
        self.service.get_province_humidity.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_invalid_province(self):
        """Test handling of invalid province name"""
        self.service.get_province_humidity.return_value = {"error": "Invalid province name: InvalidProvince"}
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid province name: InvalidProvince"})

    def test_duplicate_provinces(self):
        """Test handling of duplicate province entries"""
        self.service.get_province_humidity.return_value = {"error": "Duplicate province found: Aceh"}
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Duplicate province found: Aceh"})

    def test_missing_province(self):
        mock_data = [
            {"value": 80.0},  # Missing province
            {"province": "Bali", "value": 75.0}
        ]
        self.service.get_province_humidity.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_missing_value(self):
        mock_data = [
            {"province": "Aceh"},  # Missing value
            {"province": "Bali", "value": 80.0}
        ]
        self.service.get_province_humidity.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_serialization_error_with_invalid_value_type(self):
        mock_data = [
            {"province": "Aceh", "value": "invalid_value"},
            {"province": "Bali", "value": 75.0}
        ]
        self.service.get_province_humidity.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_empty_data(self):
        self.service.get_province_humidity.return_value = []
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "No humidity data available."})

    def test_service_returns_error_dict(self):
        self.service.get_province_humidity.return_value = {"error": "Some error occurred"}
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {"error": "Some error occurred"})

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_get_success_with_multiple_provinces(self, mock_get_humidity):
        mock_get_humidity.return_value = [
            {"province": "Aceh", "value": 80.0},  # Valid humidity value
            {"province": "Bali", "value": 75.0}   # Valid humidity value
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['id'], 'ID-AC')
        self.assertEqual(response.data[1]['id'], 'ID-BA')
        self.assertEqual(response.data[0]['value'], 80.0)
        self.assertEqual(response.data[1]['value'], 75.0)

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_get_success_with_single_province(self, mock_get_humidity):
        mock_get_humidity.return_value = [
            {"province": "DKI Jakarta", "value": 85.0}  # Valid humidity value
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], 'ID-JK')
        self.assertEqual(response.data[0]['value'], 85.0)

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_extreme_humidity_values(self, mock_get_humidity):
        mock_get_humidity.return_value = [
            {"province": "Aceh", "value": -10.0},  # Negative value
            {"province": "Bali", "value": 150.0},  # Large value
            {"province": "DKI Jakarta", "value": 80.0}  # Normal value
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        self.assertEqual(response.data[0]['value'], -10.0)
        self.assertEqual(response.data[1]['value'], 150.0)
        self.assertEqual(response.data[2]['value'], 80.0)
