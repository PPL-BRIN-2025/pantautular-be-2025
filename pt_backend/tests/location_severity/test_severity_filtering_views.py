from django.test import TestCase
from django.urls import reverse
from unittest.mock import call, patch, MagicMock
from rest_framework.test import APIClient
from pt_backend.authentication import APIKeyAuthentication
from pt_backend.services import SeverityFilteringService
from pt_backend.models import Location
from rest_framework import status


class SeverityFilteringStatsPostViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('severity-filtering-stats')
        
        # Sample response data from the service
        self.mock_results = {
            "disease_stats": [{"name": "COVID-19", "severity_counts": {"hospitalisasi": 10, "insiden": 5, "mortalitas": 2}, "total_cases": 17}],
            "province_stats": [{"name": "DKI Jakarta", "severity_counts": {"hospitalisasi": 8, "insiden": 3, "mortalitas": 1}, "total_cases": 12}],
            "city_stats": [{"name": "Jakarta", "severity_counts": {"hospitalisasi": 6, "insiden": 2, "mortalitas": 1}, "total_cases": 9}]
        }
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_diseases(self, mock_service, mock_auth):
        """Test POST with disease filter"""
        # Setup mock
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance
        
        # Make request with disease filter
        response = self.client.post(
            self.url,
            data={"diseases": ["COVID-19", "Dengue"]},
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=["COVID-19", "Dengue"],
            provinces=None,
            cities=None,
            news_portals=None,
            alert_levels=None,
            date_range=None
        )
        self.assertEqual(response.json(), self.mock_results)
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.Location.objects.filter')
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_cities_to_provinces(self, mock_service, mock_location_filter, mock_auth):
        """Test POST with locations that get converted to provinces"""
        # Setup mocks
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance
        
        # Create different mock responses for different filter calls
        mock_province_check_jakarta = MagicMock()
        mock_province_check_jakarta.exists.return_value = False
        
        mock_province_check_bandung = MagicMock()
        mock_province_check_bandung.exists.return_value = False
        
        mock_city_check_jakarta = MagicMock()
        mock_city_check_jakarta.exists.return_value = True
        
        mock_city_check_bandung = MagicMock()
        mock_city_check_bandung.exists.return_value = True
        
        # This is the critical part - creating a mock that will properly handle
        # the chained calls for values_list().distinct()
        mock_values_jakarta = MagicMock()
        mock_values_distinct_jakarta = MagicMock()
        mock_values_distinct_jakarta.return_value = ["DKI Jakarta"]
        mock_values_jakarta.distinct = MagicMock(return_value=["DKI Jakarta"])
        
        mock_values_bandung = MagicMock()
        mock_values_distinct_bandung = MagicMock()
        mock_values_distinct_bandung.return_value = ["Jawa Barat"]
        mock_values_bandung.distinct = MagicMock(return_value=["Jawa Barat"])
        
        mock_filter_jakarta = MagicMock()
        mock_filter_jakarta.values_list = MagicMock(return_value=mock_values_jakarta)
        
        mock_filter_bandung = MagicMock()
        mock_filter_bandung.values_list = MagicMock(return_value=mock_values_bandung)
        
        # Configure the mock to return different objects based on arguments
        def mock_filter_side_effect(**kwargs):
            if 'province' in kwargs:
                if kwargs['province'] == "Jakarta":
                    return mock_province_check_jakarta
                elif kwargs['province'] == "Bandung":
                    return mock_province_check_bandung
            elif 'city' in kwargs:
                if kwargs['city'] == "Jakarta":
                    return mock_filter_jakarta
                elif kwargs['city'] == "Bandung":
                    return mock_filter_bandung
            return MagicMock()
        
        mock_location_filter.side_effect = mock_filter_side_effect
        
        # Make request with locations
        response = self.client.post(
            self.url,
            data={"locations": ["Jakarta", "Bandung"]},
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Get the actual call arguments
        actual_call = mock_service_instance.get_filter_stats.call_args
        actual_kwargs = actual_call[1]
        
        # Order-independent assertions
        self.assertEqual(actual_kwargs['diseases'], None)
        self.assertCountEqual(actual_kwargs['provinces'], ['DKI Jakarta', 'Jawa Barat'])  # Order doesn't matter
        self.assertCountEqual(actual_kwargs['cities'], ['Jakarta', 'Bandung'])  # Order doesn't matter
        self.assertEqual(actual_kwargs['news_portals'], None)
        self.assertEqual(actual_kwargs['alert_levels'], None)
        self.assertEqual(actual_kwargs['date_range'], None)
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_portals(self, mock_service, mock_auth):
        """Test POST with news portals filter"""
        # Setup mock
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance
        
        # Make request with news portals
        response = self.client.post(
            self.url,
            data={"portals": ["Kompas", "Detik"]},
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,
            cities=None,
            news_portals=["Kompas", "Detik"],
            alert_levels=None,
            date_range=None
        )
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_level_of_alertness_as_string(self, mock_service, mock_auth):
        """Test POST with level_of_alertness as string that gets converted to int"""
        # Setup mock
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance
        
        # Make request with level_of_alertness as string
        response = self.client.post(
            self.url,
            data={"level_of_alertness": "2"},
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,
            cities=None,
            news_portals=None,
            alert_levels=2,  # Should be converted to integer
            date_range=None
        )
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_date_range(self, mock_service, mock_auth):
        """Test POST with date range"""
        # Setup mock
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance
        
        # Make request with date range
        response = self.client.post(
            self.url,
            data={
                "start_date": "2023-01-01",
                "end_date": "2023-12-31"
            },
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,
            cities=None,
            news_portals=None,
            alert_levels=None,
            date_range=("2023-01-01", "2023-12-31")
        )
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.Location.objects.filter')
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_all_filters(self, mock_service, mock_location_filter, mock_auth):
        """Test POST with all filter types combined"""
        # Setup mocks
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance
        
        # Mock Location.objects.filter to return different results based on arguments
        def mock_filter_side_effect(**kwargs):
            mock_filter_result = MagicMock()
            
            if 'province' in kwargs:
                # When checking if location is a province
                province_name = kwargs['province']
                # Return True only if province is "DKI Jakarta" (not for "Jakarta")
                mock_exists = MagicMock()
                mock_exists.exists.return_value = province_name == "DKI Jakarta"
                return mock_exists
            
            elif 'city' in kwargs:
                # When checking if location is a city
                city_name = kwargs['city']
                # Return True only if city is "Jakarta"
                mock_exists = MagicMock()
                mock_exists.exists.return_value = city_name == "Jakarta"
                
                # For values_list call that gets provinces for cities
                mock_values = MagicMock()
                mock_values.distinct.return_value = ["DKI Jakarta"]
                mock_filter_result.values_list.return_value = mock_values
                
                return mock_filter_result
            
            return MagicMock()
        
        mock_location_filter.side_effect = mock_filter_side_effect
        
        # Make request with all filters
        response = self.client.post(
            self.url,
            data={
                "diseases": ["COVID-19"],
                "locations": ["Jakarta"],
                "portals": ["Kompas"],
                "level_of_alertness": "3",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31"
            },
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=["COVID-19"],
            provinces=["DKI Jakarta"],
            cities=["Jakarta"],
            news_portals=["Kompas"],
            alert_levels=3,
            date_range=("2023-01-01", "2023-12-31")
        )
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_invalid_level_of_alertness(self, mock_service, mock_auth):
        """Test POST with invalid level_of_alertness"""
        # Setup mock
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service.return_value = mock_service_instance
        
        # Make request with invalid level_of_alertness
        response = self.client.post(
            self.url,
            data={"level_of_alertness": "not-a-number"},
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("invalid literal for int()", response.data["error"])
        mock_service_instance.get_filter_stats.assert_not_called()
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.Location.objects.filter')
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_empty_locations(self, mock_service, mock_location_filter, mock_auth):
        """Test POST with empty locations list"""
        # Setup mock
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance
        
        # Make request with empty locations
        response = self.client.post(
            self.url,
            data={"locations": []},
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_location_filter.assert_not_called()  # Should not query for provinces
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,
            cities=None,
            news_portals=None,
            alert_levels=None,
            date_range=None
        )
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.SeverityFilteringService.get_filter_stats')
    def test_post_with_service_exception(self, mock_get_filter_stats, mock_auth):
        """Test error handling when service raises an exception"""
        # Setup mock to raise exception
        mock_get_filter_stats.side_effect = Exception("Test service error")
        
        # Make request
        response = self.client.post(
            self.url,
            data={"diseases": ["COVID-19"]},
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Test service error", response.data["error"])
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.Location.objects.filter')
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_invalid_locations(self, mock_service, mock_location_filter, mock_auth):
        """Test POST with locations that don't match any provinces or cities"""
        # Setup mocks
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance
        
        # Mock the location filter to return False for both province and city checks
        mock_filter_result = MagicMock()
        mock_filter_result.exists.return_value = False
        mock_location_filter.return_value = mock_filter_result
        
        # Make request with invalid locations
        response = self.client.post(
            self.url,
            data={"locations": ["Unknown Location"]},
            format='json'
        )
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,  # Should be None since no provinces were found
            cities=None,     # Should be None since no cities were found
            news_portals=None,
            alert_levels=None,
            date_range=None
        )