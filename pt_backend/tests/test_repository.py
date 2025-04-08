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
        # Create test diseases
        self.disease1 = Disease.objects.create(id=uuid.uuid4(), name="COVID-19", level_of_alertness=5)
        self.disease2 = Disease.objects.create(id=uuid.uuid4(), name="Ebola", level_of_alertness=4)

        # Create test locations
        self.location1 = Location.objects.create(id=uuid.uuid4(), latitude=-6.2088, longitude=106.8456, city="Jakarta", province="DKI Jakarta")
        self.location2 = Location.objects.create(id=uuid.uuid4(), latitude=-6.9175, longitude=107.6191, city="Bandung", province="Jawa Barat")

        # Create test cases
        self.case1 = Case.objects.create(
            id=uuid.uuid4(), 
            gender="Pria", 
            age=30, 
            city="Jakarta", 
            status="kematian", 
            severity="mortalitas",
            disease=self.disease1, 
            location=self.location1
        )
        self.case2 = Case.objects.create(
            id=uuid.uuid4(), 
            gender="Wanita", 
            age=25, 
            city="Bandung", 
            status="terjangkit", 
            severity="hospitalisasi",
            disease=self.disease2, 
            location=self.location2
        )

        # Create test news
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
            title="Ebola Detected in Bandung", 
            content="Ebola case detected in Bandung...", 
            url="https://www.detik.com/ebola-bandung", 
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

    def test_get_all_severities_dates(self):
        result = self.repository.get_all_severities_dates()
        
        self.assertIn("mortalitas", result)
        self.assertIn("hospitalisasi", result)
        
        mort_data = result["mortalitas"]
        self.assertEqual(len(mort_data), 1)
        self.assertEqual(mort_data[0]["count"], 1)
        
        hosp_data = result["hospitalisasi"]
        self.assertEqual(len(hosp_data), 1)
        self.assertEqual(hosp_data[0]["count"], 1)

    def test_get_all_severities_dates_empty(self):
        News.objects.all().delete()
        
        result = self.repository.get_all_severities_dates()
        
        self.assertNotIn("mortalitas", result)
        self.assertNotIn("hospitalisasi", result)
        self.assertEqual(result, {})

class CaseRepositoryTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repository = CaseRepository()
    
    def test_get_all_cases(self):
        cases = self.repository.get_all_cases()
        self.assertEqual(cases.count(), 2)
    
    def test_get_all_cases_empty(self):
        # Clear all cases first
        News.objects.all().delete()
        Case.objects.all().delete()
        cases = self.repository.get_all_cases()
        self.assertFalse(cases.exists())
        
    def test_get_all_case_locations(self):
        locations = self.repository.get_all_locations()
        self.assertTrue(locations.exists())
        self.assertEqual(locations.count(), 2)
        

    def test_get_all_case_locations_empty(self):
        Case.objects.all().delete()
        locations = self.repository.get_all_locations()
        self.assertFalse(locations.exists())

    def test_get_cases_by_year(self):
        # Create a case with a specific year
        specific_date = timezone.make_aware(datetime(2023, 1, 1))
        case_2023 = Case.objects.create(
            id=uuid.uuid4(), 
            gender="Pria", 
            age=40, 
            city="Surabaya", 
            status="terjangkit", 
            severity="hospitalisasi",
            disease=self.disease1, 
            location=self.location1
        )
        
        News.objects.create(
            id=uuid.uuid4(), 
            portal="cnn.com", 
            type="health", 
            title="2023 Case", 
            content="2023 case content...", 
            url="https://www.cnn.com/2023",
            date_published=specific_date,            
            author="Test Author", 
            case=case_2023
        )
        
        # Test getting cases for 2023
        cases_2023 = self.repository.get_cases_by_year(2023)
        self.assertEqual(cases_2023.count(), 1)
        
        # Test getting cases for current year (should be 2 from base setup)
        current_year = timezone.now().year
        cases_current_year = self.repository.get_cases_by_year(current_year)
        self.assertEqual(cases_current_year.count(), 2)
        
        # Test getting cases for a year with no data
        cases_2020 = self.repository.get_cases_by_year(2020)
        self.assertEqual(cases_2020.count(), 0)