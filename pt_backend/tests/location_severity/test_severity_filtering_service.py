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

class CasesFilterServiceTestCase(TestCase):
    """Test class specifically for CasesFilterService"""
    
    def setUp(self):
        # Mock case service
        self.mock_case_service = MagicMock()
        self.filter_service = CasesFilterService(self.mock_case_service)
        
        # Mock the queryset for filtering operations
        self.mock_queryset = MagicMock()
        self.mock_filtered_queryset = MagicMock()
        self.mock_case_service.get_all_cases.return_value = self.mock_queryset
        
        # Set up the mock queryset to return a new mock when filter is called
        self.mock_queryset.filter.return_value = self.mock_filtered_queryset
    
    def test_filter_by_disease(self):
        """Test that _filter_by_disease properly filters cases by disease name"""
        # Test data
        disease_names = ["COVID-19", "Dengue"]
        
        # Call the method directly
        result = self.filter_service._filter_by_disease(self.mock_queryset, disease_names)
        
        # Check filter was called with correct arguments
        self.mock_queryset.filter.assert_called_once_with(disease__name__in=disease_names)
        
        # Verify result is the filtered queryset
        self.assertEqual(result, self.mock_filtered_queryset)
    
    def test_date_range_as_dictionary(self):
        """Test _filter_by_news_date_range with date_range as a dictionary"""
        # Test data with dictionary date range
        date_range = {
            'start': '2023-01-01',
            'end': '2023-12-31'
        }
        
        # Call the method directly
        result = self.filter_service._filter_by_news_date_range(self.mock_queryset, date_range)
        
        # Check that filter was called with correct arguments for date range
        self.mock_queryset.filter.assert_called_once_with(
            news__date_published__range=[date_range['start'], date_range['end']]
        )
        
        # Verify result is the filtered queryset
        self.assertEqual(result, self.mock_filtered_queryset)
    
    def test_date_range_as_dictionary_with_only_start_date(self):
        """Test _filter_by_news_date_range with dictionary containing only start date"""
        # Test data with dictionary containing only start date
        date_range = {
            'start': '2023-01-01',
            'end': None
        }
        
        # Call the method directly
        result = self.filter_service._filter_by_news_date_range(self.mock_queryset, date_range)
        
        # Check that filter was called with correct arguments for start date only
        self.mock_queryset.filter.assert_called_once_with(
            news__date_published__gte=date_range['start']
        )
        
        # Verify result is the filtered queryset
        self.assertEqual(result, self.mock_filtered_queryset)
    
    def test_date_range_as_dictionary_with_only_end_date(self):
        """Test _filter_by_news_date_range with dictionary containing only end date"""
        # Test data with dictionary containing only end date
        date_range = {
            'start': None,
            'end': '2023-12-31'
        }
        
        # Call the method directly
        result = self.filter_service._filter_by_news_date_range(self.mock_queryset, date_range)
        
        # Check that filter was called with correct arguments for end date only
        self.mock_queryset.filter.assert_called_once_with(
            news__date_published__lte=date_range['end']
        )
        
        # Verify result is the filtered queryset
        self.assertEqual(result, self.mock_filtered_queryset)
    
    def test_date_range_as_empty_dictionary(self):
        """Test _filter_by_news_date_range with an empty dictionary"""
        # Test data with empty dictionary
        date_range = {}
        
        # Call the method directly
        result = self.filter_service._filter_by_news_date_range(self.mock_queryset, date_range)
        
        # The filter should not be called since both start and end dates would be None
        self.mock_queryset.filter.assert_not_called()
        
        # Should return the original queryset
        self.assertEqual(result, self.mock_queryset)

    def test_filter_cases_with_ids_only(self):
        """Test that filter_cases returns only IDs when ids_only=True"""
        # Setup
        mock_ids_values = MagicMock()
        self.mock_queryset.values.return_value = mock_ids_values
        
        # Call the method with ids_only=True
        result = self.filter_service.filter_cases(ids_only=True)
        
        # Verify that values('id') was called on the queryset
        self.mock_queryset.values.assert_called_once_with('id')
        
        # Verify that the result is the mock_ids_values
        self.assertEqual(result, mock_ids_values)
    
    def test_date_range_as_tuple(self):
        """Test _filter_by_news_date_range with date_range as a tuple"""
        # Test data with tuple date range
        start_date = '2023-01-01'
        end_date = '2023-12-31'
        date_range = (start_date, end_date)
        
        # Call the method directly
        result = self.filter_service._filter_by_news_date_range(self.mock_queryset, date_range)
        
        # Check that filter was called with correct arguments for date range
        self.mock_queryset.filter.assert_called_once_with(
            news__date_published__range=[start_date, end_date]
        )
        
        # Verify result is the filtered queryset
        self.assertEqual(result, self.mock_filtered_queryset)
    
    def test_date_range_as_tuple_with_none_values(self):
        """Test _filter_by_news_date_range with tuple containing None values"""
        # Both None
        date_range1 = (None, None)
        result1 = self.filter_service._filter_by_news_date_range(self.mock_queryset, date_range1)
        self.mock_queryset.filter.assert_not_called()
        self.assertEqual(result1, self.mock_queryset)
        
        # Reset the mock for next test
        self.mock_queryset.filter.reset_mock()
        
        # Only start date
        date_range2 = ('2023-01-01', None)
        result2 = self.filter_service._filter_by_news_date_range(self.mock_queryset, date_range2)
        self.mock_queryset.filter.assert_called_once_with(
            news__date_published__gte='2023-01-01'
        )
        self.assertEqual(result2, self.mock_filtered_queryset)
        
        # Reset the mock for next test
        self.mock_queryset.filter.reset_mock()
        
        # Only end date
        date_range3 = (None, '2023-12-31')
        result3 = self.filter_service._filter_by_news_date_range(self.mock_queryset, date_range3)
        self.mock_queryset.filter.assert_called_once_with(
            news__date_published__lte='2023-12-31'
        )
        self.assertEqual(result3, self.mock_filtered_queryset)