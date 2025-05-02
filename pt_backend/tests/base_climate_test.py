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

class BaseClimateRepositoryTest(TestCase):
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

    def test_get_latest_climate_data_empty(self):
        """Test repository method when no data exists"""
        Climate.objects.all().delete()
        result = self.repository.get_latest_climate_data()
        self.assertEqual(len(result), 0)

class BaseClimateServiceTest(TestCase):
    def setUp(self):
        self.cache_service = CacheService()
        self.repository = ClimateRepository()
        self.service = ClimateService(repository=self.repository, cache_service=self.cache_service)
        self.service_method = None  # To be set by child classes
        self.field_name = None  # To be set by child classes
        self.expected_aceh_value = None  # To be set by child classes
        self.expected_bali_value = None  # To be set by child classes

    @patch('pt_backend.repositories.ClimateRepository.get_latest_climate_data')
    def test_get_province_data_success(self, mock_get_data):
        """Test service method to get province data"""
        mock_get_data.return_value = [
            MagicMock(province="Aceh", **{self.field_name: self.expected_aceh_value}),
            MagicMock(province="Bali", **{self.field_name: self.expected_bali_value})
        ]
        
        result = getattr(self.service, self.service_method)()
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {"id": "Aceh", "value": self.expected_aceh_value})
        self.assertEqual(result[1], {"id": "Bali", "value": self.expected_bali_value})

    @patch('pt_backend.repositories.ClimateRepository.get_latest_climate_data')
    def test_get_province_data_error(self, mock_get_data):
        """Test service method when repository raises error"""
        mock_get_data.side_effect = Exception("Database error")
        
        with patch.object(self.cache_service, 'get', return_value=None):
            result = getattr(self.service, self.service_method)()
            
            self.assertIsInstance(result, dict)
            self.assertIn("error", result)
            self.assertEqual(result["error"], "Database error")

    @patch('pt_backend.services.CacheService.get')
    @patch('pt_backend.services.CacheService.set')
    def test_cache_functionality(self, mock_set, mock_get):
        """Test cache functionality in service"""
        mock_get.return_value = None
        getattr(self.service, self.service_method)()
        mock_set.assert_called_once()
        
        mock_get.return_value = [{"id": "Test", "value": self.expected_aceh_value}]
        result = getattr(self.service, self.service_method)()
        self.assertEqual(result, [{"id": "Test", "value": self.expected_aceh_value}])

class BaseClimateViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url_name = None  # To be set by child classes
        self.url = None  # To be set by child classes
        self.expected_aceh_value = None  # To be set by child classes
        self.expected_bali_value = None  # To be set by child classes
        
        os.environ['SECRET_API_KEY'] = 'test-api-key'
        self.client.credentials(HTTP_X_API_KEY='test-api-key')

    def tearDown(self):
        os.environ.pop('SECRET_API_KEY', None)

    def test_get_success(self, mock_get_data):
        """Test successful GET request"""
        mock_get_data.return_value = [
            {"id": "Aceh", "value": self.expected_aceh_value},
            {"id": "Bali", "value": self.expected_bali_value}
        ]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 2)

    def test_service_returns_error_dict(self, mock_get_data):
        """Test when service returns error dict"""
        mock_get_data.return_value = {"error": "Some error occurred"}
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data, {"error": "Some error occurred"})

    def test_serialization_error(self, mock_get_data):
        """Test when serialization fails"""
        mock_get_data.return_value = [{"invalid_field": "value"}]
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)

    def test_authentication_required(self):
        """Test that authentication is required"""
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

class BaseHumidityRepositoryTest(BaseClimateRepositoryTest):
    def setUp(self):
        super().setUp()
        self.field_name = 'humidity'
        self.expected_aceh_value = 417.0
        self.expected_bali_value = 156.0

    def test_get_latest_climate_data(self):
        """Test repository method to get latest climate data"""
        result = self.repository.get_latest_climate_data()
        
        self.assertEqual(len(result), 2)
        
        aceh_data = next(item for item in result if item.province == self.province1)
        bali_data = next(item for item in result if item.province == self.province2)
        
        self.assertEqual(getattr(aceh_data, self.field_name), self.expected_aceh_value)
        self.assertEqual(getattr(bali_data, self.field_name), self.expected_bali_value)

class BasePrecipitationRepositoryTest(BaseClimateRepositoryTest):
    def setUp(self):
        super().setUp()
        self.field_name = 'precipitation'
        self.expected_aceh_value = 100.0
        self.expected_bali_value = 80.0

    def test_get_latest_climate_data(self):
        """Test repository method to get latest climate data"""
        result = self.repository.get_latest_climate_data()
        
        self.assertEqual(len(result), 2)
        
        aceh_data = next(item for item in result if item.province == self.province1)
        bali_data = next(item for item in result if item.province == self.province2)
        
        self.assertEqual(getattr(aceh_data, self.field_name), self.expected_aceh_value)
        self.assertEqual(getattr(bali_data, self.field_name), self.expected_bali_value)

class BaseHumidityServiceTest(BaseClimateServiceTest):
    def setUp(self):
        super().setUp()
        self.service_method = 'get_province_humidity'
        self.field_name = 'humidity'
        self.expected_aceh_value = 417.0
        self.expected_bali_value = 156.0

class BasePrecipitationServiceTest(BaseClimateServiceTest):
    def setUp(self):
        super().setUp()
        self.service_method = 'get_province_precipitation'
        self.field_name = 'precipitation'
        self.expected_aceh_value = 100.0
        self.expected_bali_value = 80.0

class BaseHumidityViewTest(BaseClimateViewTest):
    def setUp(self):
        super().setUp()
        self.url_name = 'province-humidity'
        self.url = reverse(self.url_name)
        self.expected_aceh_value = 417.0
        self.expected_bali_value = 156.0

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_get_success(self, mock_get_data):
        super().test_get_success(mock_get_data)

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_service_returns_error_dict(self, mock_get_data):
        super().test_service_returns_error_dict(mock_get_data)

    @patch('pt_backend.services.ClimateService.get_province_humidity')
    def test_serialization_error(self, mock_get_data):
        super().test_serialization_error(mock_get_data)

class BasePrecipitationViewTest(BaseClimateViewTest):
    def setUp(self):
        super().setUp()
        self.url_name = 'province-precipitation'
        self.url = reverse(self.url_name)
        self.expected_aceh_value = 100.0
        self.expected_bali_value = 80.0

    @patch('pt_backend.services.ClimateService.get_province_precipitation')
    def test_get_success(self, mock_get_data):
        super().test_get_success(mock_get_data)

    @patch('pt_backend.services.ClimateService.get_province_precipitation')
    def test_service_returns_error_dict(self, mock_get_data):
        super().test_service_returns_error_dict(mock_get_data)

    @patch('pt_backend.services.ClimateService.get_province_precipitation')
    def test_serialization_error(self, mock_get_data):
        super().test_serialization_error(mock_get_data) 