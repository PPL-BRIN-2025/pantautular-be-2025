from unittest.mock import MagicMock
from django.test import TestCase
from .models import Case, Disease, Location
from .repositories import CaseRepository
from .services import CaseService, CacheService

class CaseRepositoryTest(TestCase):
    def setUp(self):
        """
        Runs before each test. Creates test data for cases, diseases, and locations.
        """
        self.repository = CaseRepository()

        self.disease = Disease.objects.create(name="COVID-19", level_of_alertness=3)

        self.location = Location.objects.create(
            latitude=6.2088, longitude=106.8456, city="Jakarta", province="DKI Jakarta"
        )

        Case.objects.create(
            gender="Male", age=30, city="Jakarta", status="biasa",
            severity="hospitalisasi", disease=self.disease, location=self.location
        )
        Case.objects.create(
            gender="Female", age=25, city="Surabaya", status="minimal",
            severity="insiden", disease=self.disease, location=self.location
        )

    def test_get_all_cases_returns_queryset(self):
        """
        Test that get_all_cases() returns a QuerySet containing all cases.
        """
        cases = self.repository.get_all_cases()
        self.assertEqual(cases.count(), 2)
        self.assertTrue(hasattr(cases, "__iter__"))  

    def test_get_all_cases_empty_database(self):
        """
        Test that get_all_cases() returns an empty queryset when no cases exist.
        """
        Case.objects.all().delete()  
        cases = self.repository.get_all_cases()
        self.assertEqual(cases.count(), 0)
        self.assertFalse(cases.exists())

    def test_get_all_cases_contains_expected_data(self):
        """
        Test that the retrieved cases match expected values.
        """
        cases = self.repository.get_all_cases()
        cities = list(cases.values_list("city", flat=True))
        self.assertIn("Jakarta", cities)
        self.assertIn("Surabaya", cities)

class CaseServiceTest(TestCase):
    def setUp(self):
        """
        Runs before each test. Mocks repository and cache service.
        """
        # Create a mock repository
        self.mock_repository = MagicMock(spec=CaseRepository)

        # Create a mock cache service
        self.mock_cache = MagicMock(spec=CacheService)

        # Instantiate the CaseService with mocks
        self.case_service = CaseService(self.mock_repository, self.mock_cache)

        # Create a test disease and location
        self.disease = Disease.objects.create(name="COVID-19", level_of_alertness=3)
        self.location = Location.objects.create(latitude=6.2088, longitude=106.8456, city="Jakarta", province="DKI Jakarta")

        # Create test case data
        self.test_cases = [
            Case.objects.create(gender="Male", age=30, city="Jakarta", status="biasa",
                                severity="hospitalisasi", disease=self.disease, location=self.location),
            Case.objects.create(gender="Female", age=25, city="Surabaya", status="minimal",
                                severity="insiden", disease=self.disease, location=self.location)
        ]

    def test_get_all_cases_fetches_from_repository_when_cache_is_empty(self):
        """
        Test that get_all_cases() retrieves cases from the repository if the cache is empty.
        """
        # Simulate cache miss (no data in cache)
        self.mock_cache.get.return_value = None

        # Simulate repository returning cases
        self.mock_repository.get_all_cases.return_value = self.test_cases

        # Call the service
        result = self.case_service.get_all_cases()

        # Verify it fetched from repository
        self.mock_repository.get_all_cases.assert_called_once()
        self.mock_cache.set.assert_called_once_with("all_cases", self.test_cases, timeout=300)
        
        self.assertEqual(result, self.test_cases)

    def test_get_all_cases_fetches_from_cache_when_available(self):
        """
        Test that get_all_cases() retrieves cases from cache if available.
        """
        # Simulate cache hit
        self.mock_cache.get.return_value = self.test_cases

        # Call the service
        result = self.case_service.get_all_cases()

        # Verify it did not call the repository
        self.mock_repository.get_all_cases.assert_not_called()

        # Verify cache retrieval was called
        self.mock_cache.get.assert_called_once_with("all_cases")

        self.assertEqual(result, self.test_cases)

    def test_get_all_cases_returns_empty_list_when_no_cases_exist(self):
        """
        Test that get_all_cases() returns an empty list when no cases exist in cache or database.
        """
        # Simulate cache miss
        self.mock_cache.get.return_value = None

        # Simulate repository returning no cases
        self.mock_repository.get_all_cases.return_value = []

        # Call the service
        result = self.case_service.get_all_cases()

        # Verify repository was queried
        self.mock_repository.get_all_cases.assert_called_once()

        # Verify cache was updated with an empty list
        self.mock_cache.set.assert_called_once_with("all_cases", [], timeout=300)

        self.assertEqual(result, [])
