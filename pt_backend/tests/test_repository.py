from django.test import TestCase

from django.test import TestCase
from pt_backend.models import Case, Disease, Location, News
from pt_backend.repositories import DiseaseRepository, LocationRepository, NewsRepository, CaseRepository
from django.core.exceptions import ObjectDoesNotExist
import uuid
from unittest.mock import patch

class BaseTestCase(TestCase):
    def setUp(self):
        self.disease1 = Disease.objects.create(id=uuid.uuid4(), name="COVID-19", level_of_alertness=5)
        self.disease2 = Disease.objects.create(id=uuid.uuid4(), name="Ebola", level_of_alertness=4)

        self.location1 = Location.objects.create(id=uuid.uuid4(), latitude=-6.2088, longitude=106.8456, city="Jakarta")
        self.location2 = Location.objects.create(id=uuid.uuid4(), latitude=-6.9175, longitude=107.6191, city="Bandung")

        self.case1 = Case.objects.create(
            id=uuid.uuid4(), gender="Pria", age=30, city="Jakarta", status="kematian", disease=self.disease1, location=self.location1
        )
        self.case2 = Case.objects.create(
            id=uuid.uuid4(), gender="Wanita", age=25, city="Bandung", status="terjangkit", disease=self.disease2, location=self.location2
        )

        self.news1 = News.objects.create(
            id=uuid.uuid4(), portal="kompas.com", type="health", title="COVID-19 Detected in Jakarta", content="COVID-19 case detected in Jakarta...", url="https://www.kompas.com/covid-jakarta", author="Dr. Joko", case=self.case1
        )
        self.news2 = News.objects.create(
            id=uuid.uuid4(), portal="detik.com", type="health", title="SARS Detected in Medan", content="SARS case detected in Medan...", url="https://www.detik.com/sars-medan", author="Dr. Sari", case=self.case2
        )

class DiseaseRepositoryTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repository = DiseaseRepository()

    def test_get_all_diseases_name(self):
        diseases = self.repository.get_all_diseases_name()
        expected = ["COVID-19", "Ebola"]
        for disease in diseases:
            self.assertIn(disease, expected)
        self.assertEqual(len(diseases), len(expected))

    def test_get_all_diseases_name_empty(self):
        Disease.objects.all().delete()  

        diseases = self.repository.get_all_diseases_name()
        self.assertEqual(diseases, [])

    @patch('pt_backend.models.Disease.objects.values_list', side_effect=ObjectDoesNotExist)
    def test_get_all_diseases_name_exception(self, mock_get_all_diseases):
        result = self.repository.get_all_diseases_name()
        self.assertEqual(result, {"error": "Error retrieving diseases"})

class LocationRepositoryTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repository = LocationRepository()

    def test_get_all_locations_name(self):
        locations = self.repository.get_all_locations_name()
        expected = ["Jakarta", "Bandung"]
        for location in locations:
            self.assertIn(location, expected)
        self.assertEqual(len(locations), len(expected))

    def test_get_all_locations_name_empty(self):
        Location.objects.all().delete()  

        locations = self.repository.get_all_locations_name()
        self.assertEqual(locations, [])

    @patch('pt_backend.models.Location.objects.values_list', side_effect=ObjectDoesNotExist)
    def test_get_all_locations_name_exception(self, mock_get_all_locations):
        result = self.repository.get_all_locations_name()
        self.assertEqual(result, {"error": "Error retrieving locations"})

class NewsRepositoryTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repository = NewsRepository()

    def test_get_all_news_name(self):
        news = self.repository.get_all_news_name()
        expected = ["kompas.com", "detik.com"]
        for news_item in news:
            self.assertIn(news_item, expected)
        self.assertEqual(len(news), len(expected))

    def test_get_all_news_name_empty(self):
        News.objects.all().delete()  

        news = self.repository.get_all_news_name()
        self.assertEqual(news, [])

    @patch('pt_backend.models.News.objects.values_list', side_effect=ObjectDoesNotExist)
    def test_get_all_news_name_exception(self, mock_get_all_news):
        result = self.repository.get_all_news_name()
        self.assertEqual(result, {"error": "Error retrieving news"})

class CaseRepositoryTestCase(TestCase):
    def setUp(self):
        self.disease = Disease.objects.create(name="COVID-19", level_of_alertness=5)
        self.location = Location.objects.create(
            latitude=-6.9175, longitude=107.6191, city="Bandung"
        )
        self.case = Case.objects.create(
            id=uuid.uuid4(),
            gender="Female",
            age=25,
            city="Bandung",
            status="recovered",
            disease=self.disease,
            location=self.location
        )

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

        self.repository = CaseRepository()

    def test_get_all_case_locations(self):
        locations = self.repository.get_all_locations()
        self.assertTrue(locations.exists())
        self.assertEqual(locations.count(), 1)
        case_data = locations.first()
        self.assertEqual(str(case_data["id"]), str(self.case.id))
        self.assertEqual(float(case_data["location__latitude"]), -6.9175)
        self.assertEqual(float(case_data["location__longitude"]), 107.6191)
        self.assertEqual(case_data["city"], "Bandung")

    def test_get_all_case_locations_empty(self):
        Case.objects.all().delete()
        locations = self.repository.get_all_locations()
        self.assertFalse(locations.exists())

    def test_positive_case(self):
        """
        A case with one related news record should appear in the results
        with the expected fields.
        """
        # First clear all existing cases and news
        News.objects.all().delete()
        Case.objects.all().delete()
        
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
        # Clear all cases and news first
        News.objects.all().delete()
        Case.objects.all().delete()
        
        repository = CaseRepository()
        qs = repository.get_all_cases()
        results = list(qs)
        self.assertEqual(len(results), 0)

    def test_corner_case_multiple_news(self):
        """
        A case with multiple news records should return one row per news item.
        Shared fields such as case id, location, and severity should be identical.
        """
        # Clear all existing cases and news first
        News.objects.all().delete()
        Case.objects.all().delete()
        
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
