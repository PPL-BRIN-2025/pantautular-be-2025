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
from .base_climate_test import BaseTemperatureRepositoryTest, BaseTemperatureServiceTest, BaseTemperatureViewTest

class ClimateRepositoryTest(BaseTemperatureRepositoryTest):
    def setUp(self):
        self.field_name = 'temperature'
        self.expected_aceh_value = 25.5
        self.expected_bali_value = 27.0
        super().setUp()

class ClimateServiceTest(BaseTemperatureServiceTest):
    def setUp(self):
        self.field_name = 'temperature'
        self.service_method = 'get_province_temperature'
        self.expected_aceh_value = 25.5
        self.expected_bali_value = 27.0
        super().setUp()
        
    @patch('pt_backend.repositories.ClimateRepository.get_latest_climate_data')
    def test_get_province_data_success(self, mock_get_data):
        """Test service method to get province data"""
        mock_get_data.return_value = [
            MagicMock(province="Aceh", **{self.field_name: self.expected_aceh_value}),
            MagicMock(province="Bali", **{self.field_name: self.expected_bali_value})
        ]
        
        result = getattr(self.service, self.service_method)()
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {"province": "Aceh", "value": self.expected_aceh_value})
        self.assertEqual(result[1], {"province": "Bali", "value": self.expected_bali_value})

class ProvinceTemperatureViewTest(BaseTemperatureViewTest):
    def setUp(self):
        self.url_name = 'province-temperature'
        self.expected_aceh_value = 25.5
        self.expected_bali_value = 27.0
        super().setUp()

    def tearDown(self):
        # Clean up environment variable
        os.environ.pop('SECRET_API_KEY', None)

    @patch('pt_backend.services.ClimateService.get_province_temperature')
    def test_get_success(self, mock_get_temperature):
        """Test successful GET request"""
        mock_get_temperature.return_value = [
            {"province": "Aceh", "value": 25.5},
            {"province": "Bali", "value": 27.0}
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 2)
        # The response should contain ISO 3166-2 codes
        self.assertEqual(response.data['data'][0]['id'], 'ID-AC')
        self.assertEqual(response.data['data'][1]['id'], 'ID-BA')

    @patch('pt_backend.services.ClimateService.get_province_temperature')
    def test_service_returns_error_dict(self, mock_get_temperature):
        """Test when service returns error dict"""
        mock_get_temperature.return_value = {"error": "Some error occurred"}
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"error": "Some error occurred"})

    @patch('pt_backend.services.ClimateService.get_province_temperature')
    def test_serialization_error(self, mock_get_temperature):
        """Test when serialization error occurs"""
        mock_get_temperature.return_value = [
            {"province": "Aceh", "value": "invalid_value"},  # Invalid value type
            {"province": "Bali", "value": 27.0}
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)

    def test_authentication_required(self):
        """Test that authentication is required"""
        # Remove API key header
        self.client.credentials()
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
