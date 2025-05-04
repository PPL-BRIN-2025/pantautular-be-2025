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
        self.field_name = None  # To be set by child classes
        self.expected_aceh_value = None  # To be set by child classes
        self.expected_bali_value = None  # To be set by child classes
        
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
        
    def test_get_latest_climate_data(self):
        """Test repository method to get latest climate data"""
        if not self.field_name:  # Skip if field_name not set
            return
            
        result = self.repository.get_latest_climate_data()
        
        self.assertEqual(len(result), 2)
        
        aceh_data = next(item for item in result if item.province == self.province1)
        bali_data = next(item for item in result if item.province == self.province2)
        
        self.assertEqual(getattr(aceh_data, self.field_name), self.expected_aceh_value)
        self.assertEqual(getattr(bali_data, self.field_name), self.expected_bali_value)

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
        if not self.service_method or not self.field_name:  # Skip if not properly configured
            return
            
        mock_get_data.return_value = [
            MagicMock(province="Aceh", **{self.field_name: self.expected_aceh_value}),
            MagicMock(province="Bali", **{self.field_name: self.expected_bali_value})
        ]
        
        result = getattr(self.service, self.service_method)()
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {"province": "Aceh", "value": self.expected_aceh_value})
        self.assertEqual(result[1], {"province": "Bali", "value": self.expected_bali_value})

    @patch('pt_backend.repositories.ClimateRepository.get_latest_climate_data')
    def test_get_province_data_error(self, mock_get_data):
        """Test service method when repository raises error"""
        if not self.service_method:  # Skip if not properly configured
            return
            
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
        if not self.service_method or self.expected_aceh_value is None:  # Skip if not properly configured
            return
            
        mock_get.return_value = None
        getattr(self.service, self.service_method)()
        mock_set.assert_called_once()
        
        mock_get.return_value = [{"province": "Test", "value": self.expected_aceh_value}]
        result = getattr(self.service, self.service_method)()
        self.assertEqual(result, [{"province": "Test", "value": self.expected_aceh_value}])

class BaseClimateViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url_name = None  # To be set by child classes
        self.url = None  # To be set by child classes
        self.expected_aceh_value = None  # To be set by child classes
        self.expected_bali_value = None  # To be set by child classes
        self.service_method = None  # To be set by child classes to the relevant service method name
        
        os.environ['SECRET_API_KEY'] = 'test-api-key'
        self.client.credentials(HTTP_X_API_KEY='test-api-key')

    def tearDown(self):
        # Clean up environment variable
        os.environ.pop('SECRET_API_KEY', None)

    def get_patch_path(self):
        """Returns the correct patch path for the service method being tested"""
        if not self.service_method:
            return None
        return f'pt_backend.services.ClimateService.{self.service_method}'

    def test_get_success(self):
        """Test successful GET request"""
        if not self.url or not self.get_patch_path():  # Skip if not properly configured
            return
            
        patch_path = self.get_patch_path()
        with patch(patch_path) as mock_get_data:
            mock_get_data.return_value = [
                {"province": "Aceh", "value": self.expected_aceh_value},
                {"province": "Bali", "value": self.expected_bali_value}
            ]
            
            response = self.client.get(self.url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 2)
            self.assertEqual(response.data[0]['id'], 'ID-AC')
            self.assertEqual(response.data[1]['id'], 'ID-BA')

    def test_service_returns_error_dict(self):
        """Test when service returns error dict"""
        if not self.url or not self.get_patch_path():  # Skip if not properly configured
            return
            
        patch_path = self.get_patch_path()
        with patch(patch_path) as mock_get_data:
            mock_get_data.return_value = {"error": "Some error occurred"}
            
            response = self.client.get(self.url)
            
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertEqual(response.data, {"error": "Some error occurred"})

    def test_serialization_error(self):
        """Test when serialization fails"""
        if not self.url or not self.get_patch_path():  # Skip if not properly configured
            return
            
        patch_path = self.get_patch_path()
        with patch(patch_path) as mock_get_data:
            mock_get_data.return_value = [{"invalid_field": "value", "invalid_field2": "value2"}]
            
            response = self.client.get(self.url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIsInstance(response.data, list)

    def test_authentication_required(self):
        """Test that authentication is required"""
        if not self.url:  # Skip if not properly configured
            return
            
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

class BaseHumidityRepositoryTest(BaseClimateRepositoryTest):
    def setUp(self):
        self.field_name = 'humidity'
        self.expected_aceh_value = 417.0
        self.expected_bali_value = 156.0
        super().setUp()

class BasePrecipitationRepositoryTest(BaseClimateRepositoryTest):
    def setUp(self):
        self.field_name = 'precipitation'
        self.expected_aceh_value = 100.0
        self.expected_bali_value = 80.0
        super().setUp()

class BaseTemperatureRepositoryTest(BaseClimateRepositoryTest):
    def setUp(self):
        self.field_name = 'temperature'
        self.expected_aceh_value = 25.5
        self.expected_bali_value = 27.0
        super().setUp()

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

class BaseTemperatureServiceTest(BaseClimateServiceTest):
    def setUp(self):
        super().setUp()
        self.service_method = 'get_province_temperature'
        self.field_name = 'temperature'
        self.expected_aceh_value = 25.5
        self.expected_bali_value = 27.0

class BaseHumidityViewTest(BaseClimateViewTest):
    def setUp(self):
        super().setUp()
        self.url_name = 'province-humidity'
        self.url = reverse(self.url_name)
        self.service_method = 'get_province_humidity'
        self.expected_aceh_value = 417.0
        self.expected_bali_value = 156.0

class BasePrecipitationViewTest(BaseClimateViewTest):
    def setUp(self):
        super().setUp()
        self.url_name = 'province-precipitation'
        self.url = reverse(self.url_name)
        self.service_method = 'get_province_precipitation'
        self.expected_aceh_value = 100.0
        self.expected_bali_value = 80.0

class BaseTemperatureViewTest(BaseClimateViewTest):
    def setUp(self):
        super().setUp()
        self.url_name = 'province-temperature'
        self.url = reverse(self.url_name)
        self.service_method = 'get_province_temperature'
        self.expected_aceh_value = 25.5
        self.expected_bali_value = 27.0