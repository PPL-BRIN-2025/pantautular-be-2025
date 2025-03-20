from django.test import TestCase
from pt_backend.models import Case, Disease, Location
from pt_backend.repositories import CaseRepository

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
