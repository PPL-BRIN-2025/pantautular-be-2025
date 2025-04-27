from django.test import TestCase
from pt_backend.services import LocationService
from unittest.mock import MagicMock, patch

class LocationServiceTestCase(TestCase):
    def setUp(self):
        self.mock_repository = MagicMock()
        self.service = LocationService(repository=self.mock_repository)
        
    def test_get_province_severity_stats(self):
        """Test service properly calls repository"""
        # Setup mock repository return value
        expected_result = [
            {
                "name": "Test Province",
                "severity_counts": {
                    "hospitalisasi": 10,
                    "insiden": 5,
                    "mortalitas": 2
                },
                "total_cases": 17
            }
        ]
        self.mock_repository.get_province_severity_stats.return_value = expected_result
        
        # Call the service method (no parameter needed now)
        result = self.service.get_province_severity_stats()
        
        # Assert repository method was called without parameters
        self.mock_repository.get_province_severity_stats.assert_called_once_with()
        
        # Assert service returns repository result
        self.assertEqual(result, expected_result)
        
    def test_get_province_severity_stats_with_default_repository(self):
        """Test that service works with default repository"""
        with patch('pt_backend.services.LocationRepository') as mock_repo_class:
            # Setup mock repository instance and class
            mock_repo_instance = MagicMock()
            mock_repo_class.return_value = mock_repo_instance
            
            expected_result = [{"name": "Test Location"}]
            mock_repo_instance.get_province_severity_stats.return_value = expected_result
            
            # Create service with default repository
            service = LocationService()
            result = service.get_province_severity_stats()
            
            # Assert default repository was used
            mock_repo_class.assert_called_once()
            mock_repo_instance.get_province_severity_stats.assert_called_once_with()
            
            # Assert result is as expected
            self.assertEqual(result, expected_result)
    
    def test_get_city_severity_stats(self):
        """Test service properly calls repository for city stats"""
        # Setup mock repository return value
        expected_result = [
            {
                "name": "Test City",
                "severity_counts": {
                    "hospitalisasi": 8,
                    "insiden": 4,
                    "mortalitas": 1
                },
                "total_cases": 13
            }
        ]
        self.mock_repository.get_city_severity_stats.return_value = expected_result
        
        # Call the service method
        result = self.service.get_city_severity_stats()
        
        # Assert repository method was called properly
        self.mock_repository.get_city_severity_stats.assert_called_once_with()
        
        # Assert service returns repository result
        self.assertEqual(result, expected_result)
        
    def test_get_city_severity_stats_with_default_repository(self):
        """Test that city stats service works with default repository"""
        with patch('pt_backend.services.LocationRepository') as mock_repo_class:
            # Setup mock repository instance and class
            mock_repo_instance = MagicMock()
            mock_repo_class.return_value = mock_repo_instance
            
            expected_result = [{"name": "Test City", "total_cases": 10}]
            mock_repo_instance.get_city_severity_stats.return_value = expected_result
            
            # Create service with default repository
            service = LocationService()
            result = service.get_city_severity_stats()
            
            # Assert default repository was used
            mock_repo_class.assert_called_once()
            mock_repo_instance.get_city_severity_stats.assert_called_once_with()
            
            # Assert result is as expected
            self.assertEqual(result, expected_result)