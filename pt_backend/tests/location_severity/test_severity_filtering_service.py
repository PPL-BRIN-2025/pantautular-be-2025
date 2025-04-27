from django.test import TestCase
from unittest.mock import MagicMock, patch
from pt_backend.services import CasesFilterService, SeverityFilteringService
from pt_backend.repositories import DiseaseRepository, LocationRepository

class SeverityFilteringServiceTestCase(TestCase):
    def setUp(self):
        # Setup mock filter service and repositories
        self.mock_filter_service = MagicMock(spec=CasesFilterService)
        self.mock_disease_repository = MagicMock(spec=DiseaseRepository)
        self.mock_location_repository = MagicMock(spec=LocationRepository)
        
        # Create service instance
        self.service = SeverityFilteringService()
        
        # Replace real components with mocks
        self.service.filter_service = self.mock_filter_service
        self.service.disease_repository = self.mock_disease_repository
        self.service.location_repository = self.mock_location_repository
        
        # Setup mock return values
        self.filtered_case_ids = [{'id': 1}, {'id': 2}]
        self.mock_filter_service.filter_cases.return_value = self.filtered_case_ids
        
        self.mock_disease_stats = [{"name": "COVID-19", "severity_counts": {}, "total_cases": 10}]
        self.mock_province_stats = [{"name": "DKI Jakarta", "severity_counts": {}, "total_cases": 5}]
        self.mock_city_stats = [{"name": "Jakarta", "severity_counts": {}, "total_cases": 5}]
        
        self.mock_disease_repository.get_disease_severity_stats.return_value = self.mock_disease_stats
        self.mock_location_repository.get_province_severity_stats.return_value = self.mock_province_stats
        self.mock_location_repository.get_city_severity_stats.return_value = self.mock_city_stats
    
    def test_get_filter_stats_no_filters(self):
        """Test get_filter_stats with no filters specified"""
        # Call the method
        result = self.service.get_filter_stats()
        
        # Verify filter service was called correctly
        self.mock_filter_service.filter_cases.assert_called_once_with(
            None, None, None, None, None, None, ids_only=True
        )
        
        # Verify repositories were called with filtered IDs
        self.mock_disease_repository.get_disease_severity_stats.assert_called_once_with(self.filtered_case_ids)
        self.mock_location_repository.get_province_severity_stats.assert_called_once_with(self.filtered_case_ids)
        self.mock_location_repository.get_city_severity_stats.assert_called_once_with(self.filtered_case_ids)
        
        # Verify structure of result
        self.assertEqual(result["disease_stats"], self.mock_disease_stats)
        self.assertEqual(result["province_stats"], self.mock_province_stats)
        self.assertEqual(result["city_stats"], self.mock_city_stats)
    
    def test_get_filter_stats_with_all_filters(self):
        """Test get_filter_stats with all filters specified"""
        # Setup test parameters
        diseases = ["COVID-19"]
        provinces = ["DKI Jakarta"]
        cities = ["Jakarta"]
        news_portals = ["Kompas"]
        alert_levels = ["Biasa"]
        date_range = ("2023-01-01", "2023-12-31")
        
        # Call the method
        result = self.service.get_filter_stats(
            diseases=diseases,
            provinces=provinces,
            cities=cities,
            news_portals=news_portals,
            alert_levels=alert_levels,
            date_range=date_range
        )
        
        # Verify filter service was called with all parameters
        self.mock_filter_service.filter_cases.assert_called_once_with(
            diseases, provinces, cities, news_portals, alert_levels, date_range, ids_only=True
        )
        
        # Verify repositories were called with filtered IDs
        self.mock_disease_repository.get_disease_severity_stats.assert_called_once_with(self.filtered_case_ids)
        self.mock_location_repository.get_province_severity_stats.assert_called_once_with(self.filtered_case_ids)
        self.mock_location_repository.get_city_severity_stats.assert_called_once_with(self.filtered_case_ids)
        
        # Verify structure of result
        self.assertEqual(result["disease_stats"], self.mock_disease_stats)
        self.assertEqual(result["province_stats"], self.mock_province_stats)
        self.assertEqual(result["city_stats"], self.mock_city_stats)
    
    def test_integration_with_filter_service_initialization(self):
        """Test that the service properly initializes its dependencies"""
        # Create a fresh instance to test initialization
        with patch('pt_backend.services.CasesFilterService') as MockFilterService, \
             patch('pt_backend.services.CaseService') as MockCaseService, \
             patch('pt_backend.services.CacheService') as MockCacheService, \
             patch('pt_backend.services.CaseRepository') as MockCaseRepository:
            
            # Create a new service instance to test the initialization
            service = SeverityFilteringService()
            
            # Verify repository instances were created
            self.assertIsInstance(service.disease_repository, DiseaseRepository)
            self.assertIsInstance(service.location_repository, LocationRepository)
            
            # Verify filter service was created with correct dependencies
            MockFilterService.assert_called_once()
            MockCaseService.assert_called_once()
            MockCacheService.assert_called_once()
            MockCaseRepository.assert_called_once()
    
    def test_get_filter_stats_with_empty_date_range(self):
        """Test get_filter_stats with an empty date range (both start and end dates are None)"""
        # Setup test parameters with empty date range
        date_range = (None, None)
        
        # Call the method
        result = self.service.get_filter_stats(date_range=date_range)
        
        # Verify filter service was called with empty date range
        self.mock_filter_service.filter_cases.assert_called_once_with(
            None, None, None, None, None, date_range, ids_only=True
        )
        
        # Verify repositories were called with filtered IDs
        self.mock_disease_repository.get_disease_severity_stats.assert_called_once_with(self.filtered_case_ids)
        self.mock_location_repository.get_province_severity_stats.assert_called_once_with(self.filtered_case_ids)
        self.mock_location_repository.get_city_severity_stats.assert_called_once_with(self.filtered_case_ids)
        
        # Verify structure of result
        self.assertEqual(result["disease_stats"], self.mock_disease_stats)
        self.assertEqual(result["province_stats"], self.mock_province_stats)
        self.assertEqual(result["city_stats"], self.mock_city_stats)