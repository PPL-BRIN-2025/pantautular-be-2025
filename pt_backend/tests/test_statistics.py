from django.test import TestCase
from django.utils import timezone
from datetime import datetime
from ..models import Case, Disease, Location, News
from ..repositories import CaseRepository
from ..statistics import PrevalenceStatistics

class PrevalenceStatisticsTest(TestCase):
    def setUp(self):
        # Create test data
        self.disease = Disease.objects.create(
            name="Test Disease",
            level_of_alertness=1
        )
        
        self.location = Location.objects.create(
            latitude=0.0,
            longitude=0.0,
            city="Test City",
            province="Test Province"
        )
        
        # Create cases for different years
        for year in [2023, 2024]:
            case = Case.objects.create(
                gender="M",
                age=25,
                city="Test City",
                status="minimal",
                severity="insiden",
                disease=self.disease,
                location=self.location
            )
            
            News.objects.create(
                portal="Test Portal",
                title="Test News",
                type="Test Type",
                content="Test Content",
                url="http://test.com",
                author="Test Author",
                date_published=timezone.make_aware(datetime(year, 1, 1, 11, 15, 0)),
                case=case
            )

    def test_get_prevalence_statistics_default_year(self):
        repository = CaseRepository()
        statistics = PrevalenceStatistics(repository)
        result = statistics.get_prevalence_statistics()
        
        self.assertEqual(result["year"], 2024)
        self.assertEqual(result["total_cases"], 1)
        self.assertEqual(result["population"], 281603800)
        self.assertIsInstance(result["prevalence"], float)

    def test_get_prevalence_statistics_with_dates(self):
        repository = CaseRepository()
        statistics = PrevalenceStatistics(repository)
        
        start_date = '2023-01-01'
        
        result = statistics.get_prevalence_statistics(start_date)
        
        self.assertEqual(result["year"], 2023)
        self.assertEqual(result["total_cases"], 1)
        self.assertEqual(result["population"], 278696200)
        self.assertIsInstance(result["prevalence"], float)

    def test_get_prevalence_statistics_invalid_year(self):
        repository = CaseRepository()
        statistics = PrevalenceStatistics(repository)
        
        start_date = '2000-01-01'
        
        result = statistics.get_prevalence_statistics(start_date)
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Population data not available for year 2000")

    def test_get_prevalence_statistics_no_cases(self):
        # Delete all cases
        Case.objects.all().delete()
        
        repository = CaseRepository()
        statistics = PrevalenceStatistics(repository)
        result = statistics.get_prevalence_statistics()
        
        self.assertEqual(result["year"], 2024)
        self.assertEqual(result["total_cases"], 0)
        self.assertEqual(result["population"], 281603800)
        self.assertEqual(result["prevalence"], 0.0) 
    
    def test_get_prevalence_statistics_invalid_date_format(self):
        repository = CaseRepository()
        statistics = PrevalenceStatistics(repository)
        result = statistics.get_prevalence_statistics("invalid-date")
        self.assertIn("error", result)

