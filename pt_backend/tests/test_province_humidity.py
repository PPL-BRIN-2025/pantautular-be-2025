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

class ClimateRepositoryTest(TestCase):
    def setUp(self):
        self.repository = ClimateRepository()
        
        # Setup test data
        self.province1 = "Aceh"
        self.province2 = "Bali"
        
        # Create test climate data
        Climate.objects.create(
            id=uuid.uuid4(),
            province=self.province1,
            temperature=25.5,
            precipitation=100.0,
            humidity=417.0,
            year=2024,
            month=3
        )
        
        Climate.objects.create(
            id=uuid.uuid4(),
            province=self.province1,
            temperature=26.0,
            precipitation=90.0,
            humidity=400.0,
            year=2023,
            month=12
        )
        
        Climate.objects.create(
            id=uuid.uuid4(),
            province=self.province2,
            temperature=27.0,
            precipitation=80.0,
            humidity=156.0,
            year=2024,
            month=3
        )

    def test_get_latest_climate_data(self):
        """Test repository method to get latest climate data"""
        result = self.repository.get_latest_climate_data()
        
        # Verify we get correct number of records (one per province)
        self.assertEqual(len(result), 2)
        
        # Verify we get latest data for each province
        aceh_data = next(item for item in result if item.province == self.province1)
        bali_data = next(item for item in result if item.province == self.province2)
        
        self.assertEqual(aceh_data.humidity, 417.0)  # Latest data for Aceh
        self.assertEqual(bali_data.humidity, 156.0)  # Latest data for Bali

    def test_get_latest_climate_data_empty(self):
        """Test repository method when no data exists"""
        Climate.objects.all().delete()
        result = self.repository.get_latest_climate_data()
        self.assertEqual(len(result), 0)

class ClimateServiceTest(TestCase):
    def setUp(self):
        self.cache_service = CacheService()
        self.repository = ClimateRepository()
        self.service = ClimateService(repository=self.repository, cache_service=self.cache_service)

    @patch('pt_backend.repositories.ClimateRepository.get_latest_climate_data')
    def test_get_province_humidity_success(self, mock_get_data):
        """Test service method to get province humidity"""
        # Mock repository to return test data
        mock_get_data.return_value = [
            MagicMock(province="Aceh", humidity=417.0),
            MagicMock(province="Bali", humidity=156.0)
        ]
        
        result = self.service.get_province_humidity()
        
        # Verify format and data
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {"province": "Aceh", "value": 417.0})
        self.assertEqual(result[1], {"province": "Bali", "value": 156.0})

    @patch('pt_backend.repositories.ClimateRepository.get_latest_climate_data')
    def test_get_province_humidity_error(self, mock_get_data):
        """Test service method when repository raises error"""
        mock_get_data.side_effect = Exception("Database error")
        
        result = self.service.get_province_humidity()
        
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    @patch('pt_backend.services.CacheService.get')
    @patch('pt_backend.services.CacheService.set')
    def test_cache_functionality(self, mock_set, mock_get):
        """Test cache functionality in service"""
        # First call - should hit repository
        mock_get.return_value = None
        self.service.get_province_humidity()
        
        # Verify cache was set
        mock_set.assert_called_once()
        
        # Second call - should use cache
        mock_get.return_value = [{"province": "Test", "value": 100.0}]
        result = self.service.get_province_humidity()
        
        # Verify cache was used
        self.assertEqual(result, [{"province": "Test", "value": 100.0}])
