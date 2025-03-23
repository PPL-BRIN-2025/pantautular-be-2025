import datetime
from django.utils import timezone
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
        
        # Update cases with severity values for severities_dates tests
        self.case1.severity = "hospitalisasi"
        self.case1.save()
        self.case2.severity = "mortalitas"
        self.case2.save()

        # Update news1 and news2 with specific dates for testing
        self.news1.date_published = "2025-02-01T00:00:00Z"
        self.news1.save()
        self.news2.date_published = "2025-01-01T00:00:00Z"
        self.news2.save()
        
        # Create news with specific dates for testing
        self.news_date1 = News.objects.create(
            id=uuid.uuid4(),
            portal="cnn.com",
            type="health",
            title="COVID Update",
            content="New cases...",
            url="https://cnn.com/covid",
            author="Dr. Smith",
            date_published="2023-05-01T10:00:00Z",
            case=self.case1
        )
        
        self.news_date2 = News.objects.create(
            id=uuid.uuid4(),
            portal="cnn.com",
            type="health",
            title="COVID Update 2",
            content="More cases...",
            url="https://cnn.com/covid2",
            author="Dr. Smith",
            date_published="2023-05-01T14:00:00Z",
            case=self.case1
        )
        
        self.news_date3 = News.objects.create(
            id=uuid.uuid4(),
            portal="bbc.com",
            type="health",
            title="Mortality Report",
            content="Statistics...",
            url="https://bbc.com/health",
            author="Dr. Jones",
            date_published="2023-06-15T09:00:00Z",
            case=self.case2
        )

    def test_get_all_news_name(self):
        news = self.repository.get_all_news_name()
        # Update expected list to include all portal names from both initial setup and additional test setup
        expected = ["kompas.com", "detik.com", "cnn.com", "bbc.com"]
        for news_item in news:
            self.assertIn(news_item, expected)

    def test_get_all_news_name_empty(self):
        News.objects.all().delete()  

        news = self.repository.get_all_news_name()
        self.assertEqual(news, [])

    @patch('pt_backend.models.News.objects.values_list', side_effect=ObjectDoesNotExist)
    def test_get_all_news_name_exception(self, mock_get_all_news):
        result = self.repository.get_all_news_name()
        self.assertEqual(result, {"error": "Error retrieving news"})

    def test_get_all_severities_dates(self):
        result = self.repository.get_all_severities_dates()
        
        self.assertIn("hospitalisasi", result)
        self.assertIn("mortalitas", result)
        
        hosp_data = result["hospitalisasi"]
        self.assertEqual(len(hosp_data), 2)
        self.assertEqual(hosp_data[0]["date"], "2025-02-01")
        count = 0
        for item in hosp_data:
            count += item["count"]
        self.assertEqual(count, 3)
        
        mort_data = result["mortalitas"]
        self.assertEqual(len(mort_data), 2)
        self.assertTrue("date" in mort_data[0])
        self.assertEqual(mort_data[0]["count"], 1)

    def test_get_all_severities_dates_empty(self):
        News.objects.all().delete()
        
        result = self.repository.get_all_severities_dates()
        
        self.assertNotIn("hospitalisasi", result)
        self.assertNotIn("mortalitas", result)
        self.assertEqual(result, {})

    def test_get_all_severities_dates_with_none_severity(self):
        # Get results from repository method
        result = self.repository.get_all_severities_dates()
        
        # Verify that keys 'None' and '' are not in the results
        self.assertNotIn('None', result)
        self.assertNotIn('', result)
        
        # The original severity types should still be there
        self.assertIn("hospitalisasi", result)
        self.assertIn("mortalitas", result)

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
