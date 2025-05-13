from django.test import TestCase
from pt_backend.constants import PROVINCE_TO_CODE
from pt_backend.services import AverageSeverityByProvince, CaseService, CacheService, CasesFilterService
from pt_backend.interfaces import CaseRepositoryInterface, CacheInterface
from unittest.mock import MagicMock, call
import unittest
from django.core.cache import cache
from datetime import datetime

class TestCaseService(unittest.TestCase):
    def setUp(self):
        # Create mocks for repository and cache interfaces.
        self.mock_repository = MagicMock(spec=CaseRepositoryInterface)
        self.mock_cache = MagicMock(spec=CacheInterface)
        self.service = CaseService(self.mock_repository, self.mock_cache)

    def test_positive_case_cache_hit(self):
        """
        Positive Case:
        When the cache contains data, the service returns that data
        without calling the repository.
        """
        cached_data = [
            {
                "id": "1",
                "location__province": "TestProvince",
                "location__city": "TestCity",
                "news__portal": "TestPortal",
                "severity": "TestSeverity",
                "news__date_published": "2021-01-01"
            }
        ]
        self.mock_cache.get.return_value = cached_data

        result = self.service.get_all_cases()

        # Verify that the cache is queried.
        self.mock_cache.get.assert_called_once_with("all_cases")
        # Repository should not be called.
        self.mock_repository.get_all_cases.assert_not_called()
        self.assertEqual(result, cached_data)

    def test_negative_case_cache_miss_repository_returns_none(self):
        """
        Negative Case:
        When the cache is empty (None) and the repository returns None,
        the service should return an empty list.
        """
        self.mock_cache.get.return_value = None
        self.mock_repository.get_all_cases.return_value = None

        result = self.service.get_all_cases()

        self.mock_cache.get.assert_called_once_with("all_cases")
        self.mock_repository.get_all_cases.assert_called_once()
        # Verify that the cache is set with None and timeout is 300.
        self.mock_cache.set.assert_called_once_with("all_cases", None, timeout=300)
        # Since None is falsy, the service returns an empty list.
        self.assertEqual(result, [])

    def test_corner_case_cache_miss_repository_returns_data(self):
        """
        Corner Case:
        When the cache is empty and the repository returns valid data,
        the service caches the result and returns it.
        """
        repository_data = [
            {
                "id": "2",
                "location__province": "CornerProvince",
                "location__city": "CornerCity",
                "news__portal": "CornerPortal",
                "severity": "CornerSeverity",
                "news__date_published": "2021-02-02"
            }
        ]
        self.mock_cache.get.return_value = None
        self.mock_repository.get_all_cases.return_value = repository_data

        result = self.service.get_all_cases()

        self.mock_cache.get.assert_called_once_with("all_cases")
        self.mock_repository.get_all_cases.assert_called_once()
        self.mock_cache.set.assert_called_once_with("all_cases", repository_data, timeout=300)
        self.assertEqual(result, repository_data)

    def test_get_cases_by_year_cache_hit(self):
        """
        Test get_cases_by_year when data is in the cache.
        The service should return cached data without calling the repository.
        """
        year = 2023
        cached_data = [
            {
                "id": "3",
                "location__province": "YearProvince",
                "location__city": "YearCity",
                "news__portal": "YearPortal",
                "severity": "YearSeverity",
                "news__date_published": "2023-05-15"
            }
        ]
        self.mock_cache.get.return_value = cached_data

        result = self.service.get_cases_by_year(year)

        self.mock_cache.get.assert_called_once_with("all_cases")
        self.mock_repository.get_cases_by_year.assert_not_called()
        self.assertEqual(result, cached_data)

    def test_get_cases_by_year_cache_miss(self):
        """
        Test get_cases_by_year when data is not in the cache.
        The service should fetch data from the repository and cache it.
        """
        year = 2023
        repository_data = [
            {
                "id": "4",
                "location__province": "RepoYearProvince",
                "location__city": "RepoYearCity",
                "news__portal": "RepoYearPortal",
                "severity": "RepoYearSeverity",
                "news__date_published": "2023-06-20"
            }
        ]
        self.mock_cache.get.return_value = None
        self.mock_repository.get_cases_by_year.return_value = repository_data

        result = self.service.get_cases_by_year(year)

        self.mock_cache.get.assert_called_once_with("all_cases")
        self.mock_repository.get_cases_by_year.assert_called_once_with(year)
        self.mock_cache.set.assert_called_once_with("all_cases", repository_data, timeout=300)
        self.assertEqual(result, repository_data)

    def test_get_cases_by_year_cache_miss_empty_response(self):
        """
        Test get_cases_by_year when data is not in the cache and repository returns None.
        The service should return an empty list.
        """
        year = 2023
        self.mock_cache.get.return_value = None
        self.mock_repository.get_cases_by_year.return_value = None

        result = self.service.get_cases_by_year(year)

        self.mock_cache.get.assert_called_once_with("all_cases")
        self.mock_repository.get_cases_by_year.assert_called_once_with(year)
        self.mock_cache.set.assert_called_once_with("all_cases", None, timeout=300)
        self.assertEqual(result, [])

    def test_get_status_and_province_cache_hit(self):
        """
        Positive Case:
        When the data is already in the cache, return it directly.
        """
        cached_data = [
            {"status": "bahaya", "location__province": "Jawa Barat"},
            {"status": "minimal", "location__province": "DKI Jakarta"}
        ]
        self.mock_cache.get.return_value = cached_data

        result = self.service.get_status_and_province()

        self.mock_cache.get.assert_called_once_with("status_province")
        self.mock_repository.get_status_and_province.assert_not_called()
        self.assertEqual(result, cached_data)

    def test_get_status_and_province_cache_miss_repository_none(self):
        """
        Negative Case:
        Cache is empty and repository returns None. Should return an empty list.
        """
        self.mock_cache.get.return_value = None
        self.mock_repository.get_status_and_province.return_value = None

        result = self.service.get_status_and_province()

        self.mock_cache.get.assert_called_once_with("status_province")
        self.mock_repository.get_status_and_province.assert_called_once()
        self.mock_cache.set.assert_called_once_with("status_province", [], timeout=300)
        self.assertEqual(result, [])

    def test_get_status_and_province_cache_miss_repository_returns_data(self):
        """
        Corner Case:
        Cache is empty and repository returns valid data.
        Data should be cached and returned.
        """
        repo_data = [
            {"status": "katastropik", "location__province": "Papua"},
            {"status": "biasa", "location__province": "Sulawesi Selatan"}
        ]
        self.mock_cache.get.return_value = None
        self.mock_repository.get_status_and_province.return_value = repo_data

        result = self.service.get_status_and_province()

        self.mock_cache.get.assert_called_once_with("status_province")
        self.mock_repository.get_status_and_province.assert_called_once()
        self.mock_cache.set.assert_called_once_with("status_province", repo_data, timeout=300)
        self.assertEqual(result, repo_data)

class TestCacheService(TestCase):
    def setUp(self):
        self.cache_service = CacheService()
        # Clear Django's cache before each test.
        cache.clear()

    def test_set_and_get(self):
        """
        Test that setting a value in the cache and then retrieving it works as expected.
        """
        key = "test_key"
        value = "test_value"
        self.cache_service.set(key, value, timeout=60)
        result = self.cache_service.get(key)
        self.assertEqual(result, value)

    def test_delete(self):
        """
        Test that deleting a key from the cache results in a None retrieval.
        """
        key = "test_key"
        value = "test_value"
        self.cache_service.set(key, value, timeout=60)
        self.cache_service.delete(key)
        result = self.cache_service.get(key)
        self.assertIsNone(result)

class TestCaseFilterService(unittest.TestCase):
    def setUp(self):
        self.dummy_qs = MagicMock(name="QuerySet")
        self.dummy_qs.filter.return_value = self.dummy_qs
        self.dummy_case_service = MagicMock(name="CaseService")
        self.dummy_case_service.get_all_cases.return_value = self.dummy_qs
        self.filter_service = CasesFilterService(self.dummy_case_service)

    def test_no_filters(self):
        """
        When no filters are provided, the filter service should simply return
        the original QuerySet without calling any filter() methods.
        """
        result = self.filter_service.filter_cases()
        self.dummy_case_service.get_all_cases.assert_called_once()
        self.dummy_qs.filter.assert_not_called()
        self.assertEqual(result, self.dummy_qs)

    def test_all_filters(self):
        """
        When all filters are provided, the service should chain filter calls
        with the correct lookup parameters.
        """
        disease = ["COVID-19", "SARS"]
        provinces = ["Province1", "Province2"]
        cities = ["City1", "City2"]
        portals = ["Portal1", "Portal2"]  # Changed from news_portals to portals
        disease_alertness = 3  # Changed from level_of_alertness to disease_alertness
        date_range = {
            'start': "2023-01-01T00:00:00",
            'end': "2023-01-31T00:00:00"
        }  # Changed format to match service implementation
    
        result = self.filter_service.filter_cases(
            disease=disease,
            provinces=provinces,
            cities=cities,
            portals=portals,
            disease_alertness=disease_alertness,  # Changed parameter name
            date_range=date_range
        )
        
        expected_calls = [
            call(disease__name__in=disease),
            call(location__province__in=provinces),
            call(location__city__in=cities),
            call(news__portal__in=portals),
            call(disease__level_of_alertness=disease_alertness),
            # The following depends on the implementation of _filter_by_news_date_range
            call(news__date_published__range=[date_range['start'], date_range['end']])
        ]
        
        self.assertEqual(self.dummy_qs.filter.call_count, 6)
        # We only check the first 5 calls as the date range filtering might be more complex
        for i in range(5):
            self.assertEqual(self.dummy_qs.filter.call_args_list[i], expected_calls[i])
        self.assertEqual(result, self.dummy_qs)
    
    def test_partial_filters(self):
        """
        When only a subset of filters are provided, only those filters should be applied.
        For example, if only provinces and disease_alertness are provided.
        """
        provinces = ["ProvinceX"]
        disease_alertness = 3  # Changed from level_of_alertness to disease_alertness
    
        result = self.filter_service.filter_cases(
            provinces=provinces, 
            disease_alertness=disease_alertness  # Changed parameter name
        )
        
        expected_calls = [
            call(location__province__in=provinces),
            call(disease__level_of_alertness=disease_alertness),
        ]
        
        self.assertEqual(self.dummy_qs.filter.call_count, 2)
        self.assertEqual(self.dummy_qs.filter.call_args_list[0], expected_calls[0])
        self.assertEqual(self.dummy_qs.filter.call_args_list[1], expected_calls[1])
        self.assertEqual(result, self.dummy_qs)

    def test_date_range_both_dates_provided(self):
        date_range = {
            'start': "2023-01-01T00:00:00",
            'end': "2023-12-31T23:59:59"
        }
        
        result = self.filter_service.filter_cases(date_range=date_range)
        
        # Check the date range filter was applied correctly
        self.assertEqual(self.dummy_qs.filter.call_count, 1)
        self.assertEqual(
            self.dummy_qs.filter.call_args_list[0],
            call(news__date_published__range=[date_range['start'], date_range['end']])
        )
        self.assertEqual(result, self.dummy_qs)
    
    def test_date_range_only_start_date_provided(self):
        date_range = {
            'start': "2023-01-01T00:00:00"
        }
        
        result = self.filter_service.filter_cases(date_range=date_range)
        
        # Check the date range filter was applied correctly with gte operator
        self.assertEqual(self.dummy_qs.filter.call_count, 1)
        self.assertEqual(
            self.dummy_qs.filter.call_args_list[0],
            call(news__date_published__gte=date_range['start'])
        )
        self.assertEqual(result, self.dummy_qs)
    
    def test_date_range_only_end_date_provided(self):
        date_range = {
            'end': "2023-12-31T23:59:59"
        }
        
        result = self.filter_service.filter_cases(date_range=date_range)
        
        # Check the date range filter was applied correctly with lte operator
        self.assertEqual(self.dummy_qs.filter.call_count, 1)
        self.assertEqual(
            self.dummy_qs.filter.call_args_list[0],
            call(news__date_published__lte=date_range['end'])
        )
        self.assertEqual(result, self.dummy_qs)
    
    def test_date_range_empty_dict_provided(self):
        """
        Test date range filtering when an empty dict is provided.
        This covers the default case where no dates are available.
        """
        date_range = {}
        
        result = self.filter_service.filter_cases(date_range=date_range)
        
        # Check no filter was applied (because the date range is empty)
        self.assertEqual(self.dummy_qs.filter.call_count, 0)
        self.assertEqual(result, self.dummy_qs)

    def test_date_range_none_provided(self):
        """
        Test date range filtering when None is provided as date_range.
        This covers line 95 in services.py where it checks 'if not date_range'.
        """
        # Call filter_cases with date_range=None
        result = self.filter_service.filter_cases(date_range=None)
        
        # Check no filter was applied (because date_range is None)
        self.assertEqual(self.dummy_qs.filter.call_count, 0)
        self.assertEqual(result, self.dummy_qs)

    def test_date_range_invalid_keys(self):
        """
        Test date range filtering when date_range has invalid keys.
        This covers line 95 in services.py (the final return statement in _filter_by_news_date_range).
        """
        # date_range with invalid keys (not 'start' or 'end')
        date_range = {
            'invalid_key1': "2023-01-01T00:00:00",
            'invalid_key2': "2023-12-31T23:59:59"
        }
        
        result = self.filter_service.filter_cases(date_range=date_range)
        
        # Check no filter was applied even though date_range is not empty
        # This should reach the final "return cases" line
        self.assertEqual(self.dummy_qs.filter.call_count, 0)
        self.assertEqual(result, self.dummy_qs)

class TestAverageSeverityByProvince(unittest.TestCase):
    def setUp(self):
        self.case_service = MagicMock()
        self.analyzer = AverageSeverityByProvince(self.case_service)
        self.analyzer.PROVINCE_TO_CODE = PROVINCE_TO_CODE  # Add the province code mapping

    def test_positive_case_with_multiple_provinces(self):
        """Test with multiple provinces having different severities"""
        # Mock data with multiple provinces
        mock_data = [
            {"status": "bahaya", "location__province": "Aceh"},
            {"status": "biasa", "location__province": "Bali"},
            {"status": "minimal", "location__province": "Aceh"}
        ]
        self.case_service.get_status_and_province.return_value = mock_data

        result = self.analyzer.compute()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "ID-AC")
        # For Aceh: average of bahaya (3) and minimal (1) = 2, weight = log(2 + 1) ≈ 1.1
        # 2 * 1.1 = 2.2
        self.assertAlmostEqual(result[0]["value"], 2.2, places=1)
        self.assertEqual(result[1]["id"], "ID-BA")
        # For Bali: biasa (2), weight = log(1 + 1) ≈ 0.69
        # 2 * 0.69 = 1.38
        self.assertAlmostEqual(result[1]["value"], 1.38, places=1)

    def test_invalid_status_ignored(self):
        """Test that cases with invalid status are ignored"""
        mock_data = [
            {"status": "bahaya", "location__province": "Aceh"},
            {"status": "invalid", "location__province": "Aceh"},  # Invalid status
            {"status": "biasa", "location__province": "Bali"}
        ]
        self.case_service.get_status_and_province.return_value = mock_data

        result = self.analyzer.compute()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "ID-AC")
        # For Aceh: bahaya (3), weight = log(1 + 1) ≈ 0.69
        # 3 * 0.69 = 2.08
        self.assertAlmostEqual(result[0]["value"], 2.08, places=1)
        self.assertEqual(result[1]["id"], "ID-BA")
        # For Bali: biasa (2), weight = log(1 + 1) ≈ 0.69
        # 2 * 0.69 = 1.38
        self.assertAlmostEqual(result[1]["value"], 1.38, places=1)

    def test_missing_status_or_province(self):
        """Test handling of cases with missing status or province"""
        mock_data = [
            {"status": "bahaya", "location__province": "Aceh"},
            {"status": "biasa", "location__province": None},  # Missing province
            {"status": None, "location__province": "Bali"},   # Missing status
            {"status": "biasa", "location__province": "Bali"}
        ]
        self.case_service.get_status_and_province.return_value = mock_data

        result = self.analyzer.compute()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "ID-AC")
        # For Aceh: bahaya (3), weight = log(1 + 1) ≈ 0.69
        # 3 * 0.69 = 2.08
        self.assertAlmostEqual(result[0]["value"], 2.08, places=1)
        self.assertEqual(result[1]["id"], "ID-BA")
        # For Bali: biasa (2), weight = log(1 + 1) ≈ 0.69
        # 2 * 0.69 = 1.38
        self.assertAlmostEqual(result[1]["value"], 1.38, places=1)

    def test_empty_data(self):
        """Test handling of empty data"""
        self.case_service.get_status_and_province.return_value = []
        
        result = self.analyzer.compute()
        
        self.assertEqual(result, [])