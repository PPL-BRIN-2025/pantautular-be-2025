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
from .base_climate_test import BaseClimateRepositoryTest, BaseClimateServiceTest, BaseProvinceViewTest

class ClimateRepositoryTest(BaseClimateRepositoryTest):
    def setUp(self):
        self.field_name = 'humidity'
        self.expected_aceh_value = 417.0
        self.expected_bali_value = 156.0
        super().setUp()

class ClimateServiceTest(BaseClimateServiceTest):
    def setUp(self):
        self.field_name = 'humidity'
        self.service_method = 'get_province_humidity'
        self.expected_aceh_value = 417.0
        self.expected_bali_value = 156.0
        super().setUp()

class ProvinceHumidityViewTest(BaseProvinceViewTest):
    def setUp(self):
        self.url_name = 'province-humidity'
        self.expected_aceh_value = 417.0
        self.expected_bali_value = 156.0
        super().setUp()

    def test_get_success(self):
        """Test successful GET request"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 2)

    def test_service_returns_error_dict(self):
        """Test when service returns error dict"""
        mock_get_humidity = MagicMock(return_value={"error": "Some error occurred"})
        with patch('pt_backend.services.ClimateService.get_province_humidity', mock_get_humidity):
            response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"error": "Some error occurred"})

    def test_serialization_error(self):
        """Test when serialization fails"""
        mock_get_humidity = MagicMock(return_value=[{"invalid_field": "value"}])
        with patch('pt_backend.services.ClimateService.get_province_humidity', mock_get_humidity):
            response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)

    def test_authentication_required(self):
        """Test that authentication is required"""
        # Remove API key header
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
