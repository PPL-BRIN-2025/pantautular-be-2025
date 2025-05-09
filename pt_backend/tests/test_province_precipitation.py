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

class ClimateRepositoryTest(BasePrecipitationRepositoryTest):
    pass

class ClimateServiceTest(BasePrecipitationServiceTest):
    pass

class ProvincePrecipitationViewTest(BasePrecipitationViewTest):
    def tearDown(self):
        # Clean up environment variable
        os.environ.pop('SECRET_API_KEY', None)

    @patch('pt_backend.services.ClimateService.get_province_precipitation')
    def test_get_success(self, mock_get_precipitation):
        mock_get_precipitation.return_value = [
            {"province": "Aceh", "value": 100.0},
            {"province": "Bali", "value": 80.0}
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        # The response should contain ISO 3166-2 codes
        self.assertEqual(response.data[0]['id'], 'ID-AC')
        self.assertEqual(response.data[1]['id'], 'ID-BA')

    @patch('pt_backend.services.ClimateService.get_province_precipitation')
    def test_service_returns_error_dict(self, mock_get_precipitation):
        mock_get_precipitation.return_value = {"error": "Some error occurred"}
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"error": "Some error occurred"})

    @patch('pt_backend.services.ClimateService.get_province_precipitation')
    def test_serialization_error(self, mock_get_precipitation):
        mock_get_precipitation.return_value = [{"invalid_field": "value"}]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check that the API returns a valid response even with invalid data
        self.assertIsInstance(response.data, list)

    def test_authentication_required(self):
        self.client.credentials()
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
