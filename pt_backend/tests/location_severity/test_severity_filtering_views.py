from django.test import TestCase
from django.urls import reverse
from unittest.mock import call, patch, MagicMock
from rest_framework.test import APIClient
from pt_backend.authentication import APIKeyAuthentication
from pt_backend.services import SeverityFilteringService
from pt_backend.models import Location
from rest_framework import status
from datetime import datetime
import pytz
from django.core.cache import cache


class SeverityFilteringStatsPostViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('severity-filtering-stats')
        cache.clear()
        
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
            date_range=None,
            batch=None,
        )
        self.assertEqual(response.json(), self.mock_results)
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_locations_converted_to_provinces(self, mock_service, mock_auth):
        """Test POST with locations converted to provinces"""
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance

        # Mock Location.objects.filter untuk cities
        with patch('pt_backend.views.Location.objects.filter') as mock_loc_filter:
            mock_exists = MagicMock()
            mock_exists.exists.return_value = True
            mock_loc_filter.return_value = mock_exists

            response = self.client.post(
                self.url,
                data={"locations": {"cities": ["Jakarta"]}},
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,
            cities=["Jakarta"],
            news_portals=None,
            alert_levels=None,
            date_range=None,
            batch=None,
        )

    
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
            date_range=None,
            batch=None,
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
            date_range=None,
            batch=None,
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
            date_range=(
                datetime(2023, 1, 1, tzinfo=pytz.UTC),
                datetime(2023, 12, 31, tzinfo=pytz.UTC),
            ),
            batch=None,
        )

    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_invalid_time_window_returns_bad_request(self, mock_service, mock_auth):
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance

        response = self.client.post(
            self.url,
            data={"start_date": "invalid-date"},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['error']['code'], 'invalid_time_window')
        mock_service_instance.get_filter_stats.assert_not_called()
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_all_filters(self, mock_service, mock_auth):
        """Test POST with all filter types combined"""
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance

        # Mock Location.objects.filter
        with patch('pt_backend.views.Location.objects.filter') as mock_loc_filter:
            mock_exists = MagicMock()
            mock_exists.exists.return_value = True
            mock_loc_filter.return_value = mock_exists

            response = self.client.post(
                self.url,
                data={
                    "diseases": ["COVID-19"],
                    "locations": {"provinces": ["DKI Jakarta"], "cities": ["Jakarta"]},
                    "portals": ["Kompas"],
                    "level_of_alertness": "3",
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31"
                },
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=["COVID-19"],
            provinces=["DKI Jakarta"],
            cities=["Jakarta"],
            news_portals=["Kompas"],
            alert_levels=3,
            date_range=(
                datetime(2023, 1, 1, tzinfo=pytz.UTC),
                datetime(2023, 12, 31, tzinfo=pytz.UTC),
            ),
            batch=None,
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
            date_range=None,
            batch=None,
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
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_invalid_locations(self, mock_service, mock_auth):
        """Test POST with locations that don't match any provinces or cities"""
        # Setup mocks
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance
        
        # Mock Location.objects.filter untuk return False (lokasi tidak ada)
        with patch('pt_backend.views.Location.objects.filter') as mock_loc_filter:
            mock_exists = MagicMock()
            mock_exists.exists.return_value = False
            mock_loc_filter.return_value = mock_exists

            # Pastikan mengirim format locations yang benar (dictionary)
            response = self.client.post(
                self.url,
                data={"locations": {"provinces": ["Unknown Location"]}},
                format='json'
            )

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,  # Should be None since location is invalid
            cities=None,
            news_portals=None,
            alert_levels=None,
            date_range=None,
            batch=None,
        )
    
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_mixed_province_and_city_locations(self, mock_service, mock_auth):
        """Test POST with both province and city locations"""
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance

        # Mock Location.objects.filter
        with patch('pt_backend.views.Location.objects.filter') as mock_loc_filter:
            mock_exists = MagicMock()
            mock_exists.exists.return_value = True
            mock_loc_filter.return_value = mock_exists

            response = self.client.post(
                self.url,
                data={
                    "locations": {
                        "provinces": ["DKI Jakarta"],
                        "cities": ["Jakarta"]
                    }
                },
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=["DKI Jakarta"],
            cities=["Jakarta"],
            news_portals=None,
            alert_levels=None,
            date_range=None,
            batch=None,
        )
        
    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.CacheService')
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_cache_miss_and_hit(self, mock_service, mock_cache, mock_auth):
        """Test cache miss followed by cache hit behavior"""
        # Setup mocks
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance
        
        mock_cache_instance = MagicMock()
        # First call returns None (cache miss), second call returns results (cache hit)
        mock_cache_instance.get.side_effect = [None, self.mock_results]
        mock_cache.return_value = mock_cache_instance
        
        # First request - cache miss
        response1 = self.client.post(
            self.url,
            data={"diseases": ["COVID-19"]},
            format='json'
        )
        
        # Second request - should be cache hit
        response2 = self.client.post(
            self.url, 
            data={"diseases": ["COVID-19"]},
            format='json'
        )
        
        # Assertions
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        
        # Service should be called only once (first request)
        mock_service_instance.get_filter_stats.assert_called_once()
        
        # Cache should be queried twice and set once
        self.assertEqual(mock_cache_instance.get.call_count, 2)
        mock_cache_instance.set.assert_called_once()

    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_batch_filter(self, mock_service, mock_auth):
        batch_id = "11111111-1111-1111-1111-111111111111"

        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance

        response = self.client.post(
            self.url,
            data={"batch": batch_id},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,
            cities=None,
            news_portals=None,
            alert_levels=None,
            date_range=None,
            batch=batch_id,
        )

    @patch.object(APIKeyAuthentication, 'authenticate', return_value=None)
    @patch('pt_backend.views.SeverityFilteringService')
    def test_post_with_none_and_empty_data(self, mock_service, mock_auth):
        """Test handling of None and empty values in the request data"""
        mock_service_instance = MagicMock(spec=SeverityFilteringService)
        mock_service_instance.get_filter_stats.return_value = self.mock_results
        mock_service.return_value = mock_service_instance
        
        # Test with None values in request
        response = self.client.post(
            self.url,
            data={
                "diseases": None, 
                "locations": None,
                "portals": None,
                "level_of_alertness": None,
                "start_date": None,
                "end_date": None
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,
            provinces=None,
            cities=None,
            news_portals=None,
            alert_levels=None,
            date_range=None,
            batch=None,
        )
        
        # Reset mock for next test
        mock_service_instance.get_filter_stats.reset_mock()
        cache.clear()
        
        # Test with empty lists/strings
        response = self.client.post(
            self.url,
            data={
                "diseases": [], 
                "locations": {},
                "portals": [],
                "level_of_alertness": "",
                "start_date": "",
                "end_date": ""
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_service_instance.get_filter_stats.assert_called_once_with(
            diseases=None,  # Empty list should convert to None
            provinces=None,
            cities=None,
            news_portals=None,
            alert_levels=None,
            date_range=None,  # Empty strings should not be in date range
            batch=None,
        )
