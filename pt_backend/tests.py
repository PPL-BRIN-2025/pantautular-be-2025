from django.test import TestCase
from django.utils import timezone
from .models import Case, Location, Disease, News
from .repositories import CaseRepository  # Adjust the import if needed
from .services import CaseService, CacheService, CaseFilterService
from .interfaces import CaseRepositoryInterface, CacheInterface
from unittest.mock import MagicMock, call
import unittest
from django.core.cache import cache
from datetime import datetime
from .statistics import SeverityGroupingReport

class CaseRepositoryTest(TestCase):
    def setUp(self):
        # Create shared objects needed for tests.
        self.location = Location.objects.create(
            latitude=0.0,
            longitude=0.0,
            city="Test City",
            province="Test Province"
        )
        self.disease = Disease.objects.create(
            name="Test Disease",
            level_of_alertness=1
        )

    def test_positive_case(self):
        """
        A case with one related news record should appear in the results
        with the expected fields.
        """
        # Create a case
        case = Case.objects.create(
            gender="M",
            age=30,
            city="Test City",
            status="minimal",  # valid choice per model definition
            severity="hospitalisasi",  # valid choice per model definition
            disease=self.disease,
            location=self.location
        )
        # Create an associated news record
        news = News.objects.create(
            portal="Test Portal",
            title="Test Title",
            type="Test Type",
            content="Test content",
            url="https://example.com",
            author="Test Author",
            case=case,
            img_url="https://example.com/image.jpg"
        )
        repository = CaseRepository()
        qs = repository.get_all_cases()
        results = list(qs)

        # We expect exactly one row from the join.
        self.assertEqual(len(results), 1)
        entry = results[0]
        # Validate each field.
        self.assertEqual(str(entry["id"]), str(case.id))
        self.assertEqual(entry["location__province"], self.location.province)
        self.assertEqual(entry["location__city"], self.location.city)
        self.assertEqual(entry["news__portal"], news.portal)
        self.assertEqual(entry["severity"], case.severity)
        self.assertEqual(entry["news__date_published"].date(), news.date_published.date())

    def test_negative_case_empty_database(self):
        """
        When no cases exist in the database, the repository should return an empty queryset.
        """
        repository = CaseRepository()
        qs = repository.get_all_cases()
        results = list(qs)
        self.assertEqual(len(results), 0)

    def test_corner_case_multiple_news(self):
        """
        A case with multiple news records should return one row per news item.
        Shared fields such as case id, location, and severity should be identical.
        """
        case = Case.objects.create(
            gender="M",
            age=40,
            city="Corner City",
            status="biasa",
            severity="insiden",
            disease=self.disease,
            location=self.location
        )
        News.objects.create(
            portal="Portal 1",
            title="Title 1",
            type="Type 1",
            content="Content 1",
            url="https://example.com/1",
            author="Author 1",
            case=case,
            img_url="https://example.com/image1.jpg"
        )
        News.objects.create(
            portal="Portal 2",
            title="Title 2",
            type="Type 2",
            content="Content 2",
            url="https://example.com/2",
            author="Author 2",
            case=case,
            img_url="https://example.com/image2.jpg"
        )
        repository = CaseRepository()
        qs = repository.get_all_cases()
        results = list(qs)

        self.assertEqual(len(results), 2)
        portals = {entry["news__portal"] for entry in results}
        self.assertSetEqual(portals, {"Portal 1", "Portal 2"})
        for entry in results:
            self.assertEqual(str(entry["id"]), str(case.id))
            self.assertEqual(entry["location__province"], self.location.province)
            self.assertEqual(entry["location__city"], self.location.city)
            self.assertEqual(entry["severity"], case.severity)

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

class TestSeverityGroupingReport(unittest.TestCase):
    def setUp(self):
        # Create a dummy CaseFilterService with a filter_cases method.
        self.dummy_filter_service = MagicMock(name="CaseFilterService")
        self.report_service = SeverityGroupingReport(self.dummy_filter_service)

    def test_empty_filtered_cases(self):
        """
        When no cases are returned by the filter service,
        the report should show 0 total cases and an empty severity count.
        """
        self.dummy_filter_service.filter_cases.return_value = []
        report = self.report_service.generate_report()
        # Ensure the filter method was called.
        self.dummy_filter_service.filter_cases.assert_called_once()
        self.assertEqual(report["total_cases"], 0)
        self.assertEqual(report["severity_counts"], {})

    def test_all_same_severity(self):
        """
        When all filtered cases have the same severity,
        the report should correctly count the total and group by that severity.
        """
        cases = [
            {"severity": "hospitalisasi"},
            {"severity": "hospitalisasi"},
            {"severity": "hospitalisasi"}
        ]
        self.dummy_filter_service.filter_cases.return_value = cases
        report = self.report_service.generate_report()
        self.dummy_filter_service.filter_cases.assert_called_once()
        self.assertEqual(report["total_cases"], 3)
        self.assertEqual(report["severity_counts"], {"hospitalisasi": 3})

    def test_multiple_severities(self):
        """
        When filtered cases contain multiple severities,
        the report should aggregate counts correctly.
        Note: Cases with None for severity are ignored.
        """
        cases = [
            {"severity": "hospitalisasi"},
            {"severity": "insiden"},
            {"severity": "hospitalisasi"},
            {"severity": "mortalitas"},
            {"severity": "insiden"},
            {"severity": "hospitalisasi"},
            {"severity": None}  # This case should be ignored.
        ]
        self.dummy_filter_service.filter_cases.return_value = cases
        report = self.report_service.generate_report()
        self.dummy_filter_service.filter_cases.assert_called_once()
        self.assertEqual(report["total_cases"], 7)
        self.assertEqual(report["severity_counts"], {
            "hospitalisasi": 3,
            "insiden": 2,
            "mortalitas": 1
        })