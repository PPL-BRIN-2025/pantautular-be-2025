from django.test import TestCase
from pt_backend.services import CaseService, CacheService, CaseFilterService
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
        self.filter_service = CaseFilterService(self.dummy_case_service)

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
        provinces = ["Province1", "Province2"]
        cities = ["City1", "City2"]
        news_portals = ["Portal1", "Portal2"]
        severities = ["High", "Low"]
        start_date_str = "2023-01-01T00:00:00"
        end_date_str = "2023-01-31T00:00:00"
        news_date_range = (start_date_str, end_date_str)

        result = self.filter_service.filter_cases(
            provinces=provinces,
            cities=cities,
            news_portals=news_portals,
            severities=severities,
            news_date_range=news_date_range
        )
        expected_calls = [
            call(location__province__in=provinces),
            call(location__city__in=cities),
            call(news__portal__in=news_portals),
            call(severity__in=severities),
            call(news__date_published__range=(
                datetime.fromisoformat(start_date_str),
                datetime.fromisoformat(end_date_str)
            ))
        ]
        self.assertEqual(self.dummy_qs.filter.call_count, 5)
        self.assertEqual(self.dummy_qs.filter.call_args_list, expected_calls)
        self.assertEqual(result, self.dummy_qs)

    def test_partial_filters(self):
        """
        When only a subset of filters are provided, only those filters should be applied.
        For example, if only provinces and severities are provided.
        """
        provinces = ["ProvinceX"]
        severities = ["Medium"]

        result = self.filter_service.filter_cases(provinces=provinces, severities=severities)
        expected_calls = [
            call(location__province__in=provinces),
            call(severity__in=severities),
        ]
        self.assertEqual(self.dummy_qs.filter.call_count, 2)
        self.assertEqual(self.dummy_qs.filter.call_args_list, expected_calls)
        self.assertEqual(result, self.dummy_qs)