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
from ..views import ProvinceTemperatureView

class ClimateRepositoryTest(BaseTemperatureRepositoryTest):
    pass

class ClimateServiceTest(BaseTemperatureServiceTest):
    pass

class ProvinceTemperatureViewTest(BaseTemperatureViewTest):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.view = ProvinceTemperatureView()
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

    def _make_request(self, mock_data):
        """Helper method to make a request with mock data"""
        self.service.get_province_temperature.return_value = mock_data
        return self.view.get(self.request)

    def test_unexpected_exception(self):
        self.service.get_province_temperature.side_effect = Exception("Unexpected error")
        response = self._make_request(None)
        
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {"error": "Unexpected error"})

    def test_successful_response(self):
        mock_data = [
            {"province": "Aceh", "value": 25.0},
            {"province": "Bali", "value": 30.0}
        ]
        response = self._make_request(mock_data)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["id"], "ID-AC")
        self.assertEqual(response.data[0]["value"], 25.0)
        self.assertEqual(response.data[1]["id"], "ID-BA")
        self.assertEqual(response.data[1]["value"], 30.0)

    def test_serialization_error(self):
        response = self._make_request([{"invalid": "data"}])
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_invalid_temperature_value(self):
        response = self._make_request([{"province": "Aceh", "value": "invalid"}])
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_invalid_province(self):
        response = self._make_request({"error": "Invalid province name: InvalidProvince"})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"error": "Invalid province name: InvalidProvince"})

    def test_duplicate_provinces(self):
        response = self._make_request({"error": "Duplicate province found: Aceh"})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"error": "Duplicate province found: Aceh"})

    def test_missing_province(self):
        response = self._make_request([
            {"value": 25.0},  # Missing province
            {"province": "Bali", "value": 30.0}
        ])
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_missing_value(self):
        response = self._make_request([
            {"province": "Aceh"},  # Missing value
            {"province": "Bali", "value": 25.0}
        ])
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_serialization_error_with_invalid_value_type(self):
        response = self._make_request([
            {"province": "Aceh", "value": "invalid_value"},
            {"province": "Bali", "value": 30.0}
        ])
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid data format"})

    def test_empty_data(self):
        response = self._make_request([])
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "No temperature data available."})

    def test_service_returns_error_dict(self):
        response = self._make_request({"error": "Some error occurred"})
        
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {"error": "Some error occurred"})

    def test_invalid_province_name(self):
        mock_data = {"error": "Invalid province name: InvalidProvince"}
        self.service.get_province_temperature.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"error": "Invalid province name: InvalidProvince"})

    def test_duplicate_provinces(self):
        mock_data = {"error": "Duplicate province found: Aceh"}
        self.service.get_province_temperature.return_value = mock_data
        
        response = self.view.get(self.request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"error": "Duplicate province found: Aceh"})
