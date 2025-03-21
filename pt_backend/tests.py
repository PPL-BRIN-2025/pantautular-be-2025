from django.test import TestCase
from django.utils import timezone
from .models import Case, Location, Disease, News
from .repositories import CaseRepository  # Adjust the import if needed


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
            url="http://example.com",
            author="Test Author",
            case=case,
            img_url="http://example.com/image.jpg"
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
        # Since date_published is auto-set, we compare dates.
        self.assertEqual(entry["news__date_published"].date(), news.date_published.date())

    def test_negative_case(self):
        """
        A case without any related news should also appear
        """
        # Create a case without a related news record.
        Case.objects.create(
            gender="F",
            age=25,
            city="No News City",
            status="bahaya",
            severity="mortalitas",
            disease=self.disease,
            location=self.location
        )
        repository = CaseRepository()
        qs = repository.get_all_cases()
        results = list(qs)

        self.assertEqual(len(results), 1)

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
