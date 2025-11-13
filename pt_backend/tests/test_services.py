from django.test import TestCase
from pt_backend.constants import PROVINCE_TO_CODE
from pt_backend.services import AverageSeverityByProvince, CaseService, CacheService, CasesFilterService
from pt_backend.interfaces import CaseRepositoryInterface, CacheInterface
from pt_backend.models import Case, Disease, Location, News, CaseUploadBatch, User
from pt_backend.repositories import CaseRepository
from unittest.mock import MagicMock, call
import unittest
from django.core.cache import cache
from datetime import datetime
from django.db.models import Q
from django.utils import timezone

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
        self.mock_repository.get_all_cases.assert_called_once_with(batch_id=None)
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
        self.mock_repository.get_all_cases.assert_called_once_with(batch_id=None)
        self.mock_cache.set.assert_called_once_with("all_cases", repository_data, timeout=300)
        self.assertEqual(result, repository_data)

    def test_get_all_cases_with_batch_uses_namespaced_cache_key(self):
        batch_id = "11111111-1111-1111-1111-111111111111"
        self.mock_cache.get.return_value = None
        self.mock_repository.get_all_cases.return_value = []

        self.service.get_all_cases(batch_id=batch_id)

        namespaced_key = f"all_cases:{batch_id}"
        self.mock_cache.get.assert_called_once_with(namespaced_key)
        self.mock_repository.get_all_cases.assert_called_once_with(batch_id=batch_id)
        self.mock_cache.set.assert_called_once_with(namespaced_key, [], timeout=300)

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
        
        self.assertEqual(self.dummy_qs.filter.call_count, 6)
        calls = self.dummy_qs.filter.call_args_list
        self.assertEqual(calls[0], call(disease__name__in=disease))

        expected_province_q = Q()
        for province in provinces:
            expected_province_q |= Q(location__province__iexact=province)
        self.assertEqual(str(calls[1].args[0]), str(expected_province_q))

        expected_city_q = Q()
        for city in cities:
            expected_city_q |= Q(location__city__iexact=city) | Q(city__iexact=city)
        self.assertEqual(str(calls[2].args[0]), str(expected_city_q))

        self.assertEqual(calls[3], call(news__portal__in=portals))
        self.assertEqual(calls[4], call(disease__level_of_alertness=disease_alertness))
        self.assertEqual(
            calls[5],
            call(news__date_published__range=[date_range['start'], date_range['end']]),
        )
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
        
        province_q = Q()
        for province in provinces:
            province_q |= Q(location__province__iexact=province)

        self.assertEqual(self.dummy_qs.filter.call_count, 2)
        self.assertEqual(
            str(self.dummy_qs.filter.call_args_list[0].args[0]),
            str(province_q),
        )
        self.assertEqual(
            self.dummy_qs.filter.call_args_list[1],
            call(disease__level_of_alertness=disease_alertness),
        )
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
    
    def test_filter_by_cities_only(self):
        cities = ["CityA", "CityB"]
        
        result = self.filter_service.filter_cases(cities=cities)
        
        # Verify the correct filter was applied
        self.dummy_qs.filter.assert_called_once()
        applied_q = self.dummy_qs.filter.call_args[0][0]
        expected_q = Q()
        for city in cities:
            expected_q |= Q(location__city__iexact=city) | Q(city__iexact=city)
        self.assertEqual(str(applied_q), str(expected_q))
        self.assertEqual(result, self.dummy_qs)

class CasesFilterServiceIntegrationTests(TestCase):
    def setUp(self):
        self.disease = Disease.objects.create(name="DBD", level_of_alertness=2)
        self.loc_jakarta = Location.objects.create(city="Jakarta", province="DKI Jakarta")
        self.loc_bandung = Location.objects.create(city="Kab. Bandung", province="Jawa Barat")

        self.case_jakarta = Case.objects.create(
            gender="male",
            age=32,
            city="Jakarta",
            status="biasa",
            severity="hospitalisasi",
            disease=self.disease,
            location=self.loc_jakarta,
        )
        self.case_bandung = Case.objects.create(
            gender="female",
            age=27,
            city="Bandung",
            status="minimal",
            severity="insiden",
            disease=self.disease,
            location=self.loc_bandung,
        )

        self.expert = User.objects.create(
            name="Expert User",
            password="secret",
            role="EXPERT",
            email="expert@example.com",
        )
        self.batch_one = CaseUploadBatch.objects.create(uploaded_by=self.expert, filename="batch1.csv")
        self.batch_two = CaseUploadBatch.objects.create(uploaded_by=self.expert, filename="batch2.csv")
        self.case_jakarta.batch = self.batch_one
        self.case_jakarta.save(update_fields=["batch"])
        self.case_bandung.batch = self.batch_two
        self.case_bandung.save(update_fields=["batch"])

        News.objects.create(
            case=self.case_jakarta,
            portal="Portal1",
            title="News Jakarta",
            type="nasional",
            content="c",
            url="https://example.com/jakarta",
            author="Author J",
            date_published=timezone.now(),
            img_url="https://example.com/jakarta.jpg",
        )
        News.objects.create(
            case=self.case_bandung,
            portal="Portal2",
            title="News Bandung",
            type="lokal",
            content="c",
            url="https://example.com/bandung",
            author="Author B",
            date_published=timezone.now(),
            img_url="https://example.com/bandung.jpg",
        )

        class DirectCaseService:
            @staticmethod
            def get_all_cases(batch_id=None):
                return CaseRepository().get_all_cases(batch_id=batch_id)

        self.filter_service = CasesFilterService(case_service=DirectCaseService())

    def test_filter_by_city_matches_case_city_field(self):
        filtered = list(self.filter_service.filter_cases(cities=["Bandung"]))
        filtered_ids = {row["id"] for row in filtered}
        self.assertEqual(filtered_ids, {self.case_bandung.id})

    def test_filter_by_city_does_not_return_non_matching_locations(self):
        filtered = list(self.filter_service.filter_cases(cities=["Bandung"]))
        filtered_ids = {row["id"] for row in filtered}
        self.assertNotIn(self.case_jakarta.id, filtered_ids)
        self.assertEqual(len(filtered_ids), 1)

    def test_filter_by_combined_locations_payload(self):
        locations = {
            "provinces": ["dki jakarta", "DKI Jakarta"],
            "cities": [{"value": "bandung"}, {"label": "Jakarta"}],
        }

        filtered = list(self.filter_service.filter_cases(locations=locations))
        filtered_ids = {row["id"] for row in filtered}

        # Both province and city filters should apply, duplicates should not break the query
        self.assertEqual(filtered_ids, {self.case_jakarta.id, self.case_bandung.id})

    def test_filter_by_batch_returns_only_selected_cases(self):
        filtered = list(self.filter_service.filter_cases(batch=str(self.batch_one.id)))
        filtered_ids = {row["id"] for row in filtered}
        self.assertEqual(filtered_ids, {self.case_jakarta.id})


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
