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
    pass

class ClimateServiceTest(BaseTemperatureServiceTest):
    pass

class ProvinceTemperatureViewTest(BaseTemperatureViewTest):
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
