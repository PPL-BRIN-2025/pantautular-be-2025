from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from pt_backend.views import INTERNAL_SERVER_ERR_MSG
from ..models import Climate
from ..repositories import ClimateRepository
from ..services import ClimateService, CacheService
import uuid
from unittest.mock import patch, MagicMock
import os
from .base_climate_test import BaseHumidityRepositoryTest, BaseHumidityServiceTest, BaseHumidityViewTest

class ClimateRepositoryTest(BaseHumidityRepositoryTest):
    pass

class ClimateServiceTest(BaseHumidityServiceTest):
    pass

class ProvinceHumidityViewTest(BaseHumidityViewTest):
    def tearDown(self):
        # Clean up environment variable
        os.environ.pop('SECRET_API_KEY', None)

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_unexpected_exception(self, mock_get_humidity):
        # Configure mock to raise an unexpected exception
        mock_get_humidity.side_effect = Exception("Unexpected error")
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"error": INTERNAL_SERVER_ERR_MSG})

    # Positive Test Cases
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

    # Negative Test Cases
    def test_authentication_required(self):
        self.client.credentials()
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_service_returns_error_dict(self, mock_get_humidity):
        mock_get_humidity.return_value = {"error": "Some error occurred"}
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"error": "Some error occurred"})

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_serialization_error(self, mock_get_humidity):
        mock_get_humidity.return_value = [{"invalid_field": "value", "invalid_field2": "value2"}]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('Missing province field', response.data['error'])

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_serialization_error_with_invalid_value_type(self, mock_get_humidity):
        mock_get_humidity.return_value = [
            {"province": "Aceh", "value": "invalid_value"},
            {"province": "Bali", "value": 75.0}
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('Invalid humidity value type', response.data['error'])

    # Edge Cases
    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_empty_data(self, mock_get_humidity):
        mock_get_humidity.return_value = []
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_missing_province(self, mock_get_humidity):
        mock_get_humidity.return_value = [
            {"value": 80.0},  # Missing province
            {"province": "Bali", "value": 75.0}
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('Missing province field', response.data['error'])

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_missing_value(self, mock_get_humidity):
        mock_get_humidity.return_value = [
            {"province": "Aceh"},  # Missing value
            {"province": "Bali", "value": 75.0}
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('Missing value field', response.data['error'])

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_invalid_province_name(self, mock_get_humidity):
        mock_get_humidity.return_value = [
            {"province": "InvalidProvince", "value": 80.0},
            {"province": "Bali", "value": 75.0}
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('Invalid province name', response.data['error'])

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_extreme_humidity_values(self, mock_get_humidity):
        mock_get_humidity.return_value = [
            {"province": "Aceh", "value": -10.0},  # Below minimum
            {"province": "Bali", "value": 150.0},  # Above maximum
            {"province": "DKI Jakarta", "value": 85.0}  # Valid value
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('Invalid humidity value', response.data['error'])

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_duplicate_provinces(self, mock_get_humidity):
        mock_get_humidity.return_value = [
            {"province": "Aceh", "value": 80.0},
            {"province": "Aceh", "value": 75.0},  # Duplicate province
            {"province": "Bali", "value": 85.0}
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('Duplicate province entries', response.data['error'])
