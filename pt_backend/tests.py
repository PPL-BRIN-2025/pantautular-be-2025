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
            url="http://example.com/1",
            author="Author 1",
            case=case,
            img_url="http://example.com/image1.jpg"
        )
        News.objects.create(
            portal="Portal 2",
            title="Title 2",
            type="Type 2",
            content="Content 2",
            url="http://example.com/2",
            author="Author 2",
            case=case,
            img_url="http://example.com/image2.jpg"
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
