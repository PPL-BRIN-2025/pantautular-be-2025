from django.test import TestCase
from pt_backend.models import Case, Disease, Location, News
from pt_backend.repositories import DiseaseRepository, LocationRepository, NewsRepository, CaseRepository
from django.core.exceptions import ObjectDoesNotExist
import uuid
from unittest.mock import patch
from datetime import datetime
from django.utils import timezone

class BaseTestCase(TestCase):
    def setUp(self):
        self.disease1 = Disease.objects.create(id=uuid.uuid4(), name="COVID-19", level_of_alertness=5)
        self.disease2 = Disease.objects.create(id=uuid.uuid4(), name="Ebola", level_of_alertness=4)

        self.location1 = Location.objects.create(id=uuid.uuid4(), latitude=-6.2088, longitude=106.8456, city="Jakarta")
        self.location2 = Location.objects.create(id=uuid.uuid4(), latitude=-6.9175, longitude=107.6191, city="Bandung")

        self.case1 = Case.objects.create(
            id=uuid.uuid4(), 
            gender="Pria", 
            age=30, 
            city="Jakarta", 
            status="kematian", 
            disease=self.disease1, 
            location=self.location1
        )
        self.case2 = Case.objects.create(
            id=uuid.uuid4(), 
            gender="Wanita", 
            age=25, 
            city="Bandung", 
            status="terjangkit", 
            disease=self.disease2, 
            location=self.location2
        )

        self.news1 = News.objects.create(
            id=uuid.uuid4(), 
            portal="kompas.com", 
            type="health", 
            title="COVID-19 Detected in Jakarta", 
            content="COVID-19 case detected in Jakarta...", 
            url="https://www.kompas.com/covid-jakarta",
            date_published=timezone.now(),            
            author="Dr. Joko", 
            case=self.case1
        )
        self.news2 = News.objects.create(
            id=uuid.uuid4(), 
            portal="detik.com", 
            type="health", 
            title="SARS Detected in Medan", 
            content="SARS case detected in Medan...", 
            url="https://www.detik.com/sars-medan", 
            date_published=timezone.now(),            
            author="Dr. Sari", 
            case=self.case2
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
        self.assertEqual(hosp_data[0]["date"], "2023-05-01")
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
        self.repository = CaseRepository()
        
        # Create test disease
        self.disease1 = Disease.objects.create(
            name="COVID-19", 
            level_of_alertness=5
        )
        
        # Create test location
        self.location1 = Location.objects.create(
            latitude=-6.9175, 
            longitude=107.6191, 
            city="Bandung"
        )
        
        # Create test case
        self.case = Case.objects.create(
            id=uuid.uuid4(),
            gender="Female",
            age=25,
            city="Bandung",
            status="recovered",
            disease=self.disease1,
            location=self.location1
        )

        # Create additional test objects
        self.location2 = Location.objects.create(
            latitude=0.0,
            longitude=0.0,
            city="Test City",
            province="Test Province"
        )
        
        self.disease2 = Disease.objects.create(
            name="Test Disease",
            level_of_alertness=1
        )

        # Create test news
        self.news = News.objects.create(
            id=uuid.uuid4(), 
            portal="kompas.com", 
            type="health", 
            title="COVID-19 Detected in Jakarta", 
            content="COVID-19 case detected in Jakarta...", 
            url="https://www.kompas.com/covid-jakarta", 
            date_published=timezone.make_aware(datetime(2023, 1, 1, 11, 15, 0)),            
            author="Dr. Joko", 
            case=self.case
        )
    
    def test_get_all_cases(self):
        cases = self.repository.get_all_cases()
        self.assertEqual(cases.count(), 1)
    
    def test_get_all_cases_empty(self):
        # Clear all cases first
        News.objects.all().delete()
        Case.objects.all().delete()
        cases = self.repository.get_all_cases()
        self.assertFalse(cases.exists())
        
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
        # Clear all cases and locations first
        News.objects.all().delete()
        Case.objects.all().delete()
        
        # Create a new repository instance to ensure we're testing with a clean state
        empty_repository = CaseRepository()
        locations = empty_repository.get_all_locations()
        self.assertFalse(locations.exists())

    def test_positive_case(self):
        # Create a new location and disease for this test
        location = Location.objects.create(
            latitude=0.0, longitude=0.0, city="Test City", province="Test Province"
        )
        disease = Disease.objects.create(name="Test Disease", level_of_alertness=1)

        case = Case.objects.create(
            gender="M",
            age=30,
            city="Test City",
            status="minimal",
            severity="hospitalisasi",
            disease=disease,
            location=location
        )

        # Add date_published field to fix NOT NULL constraint error
        news = News.objects.create(
            portal="Test Portal",
            title="Test Title",
            type="Test Type",
            content="Test content",
            url="https://example.com",
            author="Test Author",
            case=case,
            img_url="https://example.com/image.jpg",
            date_published=timezone.now()  # Add this field
        )

        repository = CaseRepository()
        results = list(repository.get_all_cases())

        # We expect 2 results: one from setUp and one from this test
        self.assertEqual(len(results), 2)
        # Find the entry that matches our case ID
        entry = next((item for item in results if str(item["id"]) == str(case.id)), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["location__province"], location.province)
        self.assertEqual(entry["location__city"], location.city)
        self.assertEqual(entry["news__portal"], news.portal)
        self.assertEqual(entry["severity"], case.severity)
        self.assertEqual(entry["news__date_published"].date(), news.date_published.date())

    def test_negative_case_empty_database(self):
        # Clear all existing data to ensure we're testing with an empty database
        News.objects.all().delete()
        Case.objects.all().delete()
        Disease.objects.all().delete()
        Location.objects.all().delete()
        
        repository = CaseRepository()
        results = list(repository.get_all_cases())
        self.assertEqual(len(results), 0)

    def test_corner_case_multiple_news(self):
        # Create a new location and disease for this test
        location = Location.objects.create(
            latitude=1.0, longitude=1.0, city="Corner City", province="Corner Province"
        )
        disease = Disease.objects.create(name="Corner Disease", level_of_alertness=2)

        case = Case.objects.create(
            gender="M",
            age=40,
            city="Corner City",
            status="biasa",
            severity="insiden",
            disease=disease,
            location=location
        )

        # Add date_published field to fix NOT NULL constraint error
        News.objects.create(
            portal="Portal 1",
            title="Title 1",
            type="Type 1",
            content="Content 1",
            url="https://example.com/1",
            author="Author 1",
            case=case,
            img_url="https://example.com/image1.jpg",
            date_published=timezone.now()  # Add this field
        )

        # Add date_published field to fix NOT NULL constraint error
        News.objects.create(
            portal="Portal 2",
            title="Title 2",
            type="Type 2",
            content="Content 2",
            url="https://example.com/2",
            author="Author 2",
            case=case,
            img_url="https://example.com/image2.jpg",
            date_published=timezone.now()  # Add this field
        )

        repository = CaseRepository()
        # Get only the cases related to the current test case
        results = [result for result in repository.get_all_cases() if str(result["id"]) == str(case.id)]

        self.assertEqual(len(results), 2)
        portals = {entry["news__portal"] for entry in results}
        self.assertSetEqual(portals, {"Portal 1", "Portal 2"})

        for entry in results:
            self.assertEqual(str(entry["id"]), str(case.id))
            self.assertEqual(entry["location__province"], location.province)
            self.assertEqual(entry["location__city"], location.city)
            self.assertEqual(entry["severity"], case.severity)