from django.test import TestCase
from django.utils import timezone
from datetime import datetime
from unittest.mock import Mock, patch
from ..models import Case, Disease, Location, News
from ..repositories import CaseRepository
from ..statistics import PrevalenceStatistics, StatisticsCoordinator

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
                url="https://test.com",
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

    def test_get_prevalence_statistics_with_start_date(self):
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
        
    @patch('pt_backend.statistics.datetime')
    def test_get_prevalence_statistics_with_mocked_date(self, mock_datetime):
        # Mock the datetime.strptime to return a specific date
        mock_datetime.strptime.return_value = datetime(2023, 1, 1)
        
        repository = CaseRepository()
        statistics = PrevalenceStatistics(repository)
        
        start_date = '2023-01-01'
        
        result = statistics.get_prevalence_statistics(start_date)
        
        # Verify that strptime was called with the correct arguments
        mock_datetime.strptime.assert_called_once_with(start_date, '%Y-%m-%d')
        
        # Verify the result
        self.assertEqual(result["year"], 2023)
        self.assertEqual(result["total_cases"], 1)
        self.assertEqual(result["population"], 278696200)

class StatisticsCoordinatorTest(TestCase):
    def setUp(self):
        # Create a mock case filter service
        self.mock_case_filter_service = Mock()
        self.mock_case_filter_service.repository = Mock()
        
        # Create a mock prevalence statistics
        self.mock_prevalence = Mock()
        self.mock_prevalence.get_prevalence_statistics.return_value = {
            "year": 2023,
            "total_cases": 100,
            "population": 278696200,
            "prevalence": 0.0359
        }
        
        # Patch the PrevalenceStatistics class
        self.prevalence_patcher = patch('pt_backend.statistics.PrevalenceStatistics')
        self.mock_prevalence_class = self.prevalence_patcher.start()
        self.mock_prevalence_class.return_value = self.mock_prevalence
        
        # Create the coordinator
        self.coordinator = StatisticsCoordinator(self.mock_case_filter_service)
        
    def tearDown(self):
        self.prevalence_patcher.stop()
        
    def test_generate_comprehensive_report_with_start_date(self):
        """Test that start_date is correctly passed to get_prevalence_statistics"""
        # Call the method with a start_date
        result = self.coordinator.generate_comprehensive_report(
            date_range={"start": "2023-01-01", "end": None}
        )
        
        # Verify that get_prevalence_statistics was called with the correct start_date
        self.mock_prevalence.get_prevalence_statistics.assert_called_once_with("2023-01-01")
        
        # Verify the result
        self.assertIn("prevalence_statistics", result)
        self.assertEqual(result["prevalence_statistics"]["year"], 2023)
        
    def test_generate_comprehensive_report_without_start_date(self):
        """Test that None is passed to get_prevalence_statistics when no start_date is provided"""
        # Call the method without a start_date
        result = self.coordinator.generate_comprehensive_report()
        
        # Verify that get_prevalence_statistics was called with None
        self.mock_prevalence.get_prevalence_statistics.assert_called_once_with(None)
        
        # Verify the result
        self.assertIn("prevalence_statistics", result)
        self.assertEqual(result["prevalence_statistics"]["year"], 2023)
        
    def test_generate_comprehensive_report_with_date_range(self):
        """Test that both start_date and end_date are correctly extracted from date_range"""
        # Call the method with both start_date and end_date
        result = self.coordinator.generate_comprehensive_report(
            date_range={"start": "2023-01-01", "end": "2023-12-31"}
        )
        
        # Verify that get_prevalence_statistics was called with the correct start_date
        self.mock_prevalence.get_prevalence_statistics.assert_called_once_with("2023-01-01")
        
        # Verify the result
        self.assertIn("prevalence_statistics", result)
        self.assertEqual(result["prevalence_statistics"]["year"], 2023)

