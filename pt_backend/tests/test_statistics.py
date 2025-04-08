from django.test import TestCase
from django.utils import timezone
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
from ..models import Case, Disease, Location, News
from ..repositories import CaseRepository
from ..statistics import PrevalenceStatistics, StatisticsCoordinator, AgeGroupingReport, GenderGroupingReport, SeverityGroupingReport
import unittest

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

class TestSeverityGroupingReport(unittest.TestCase):
    def setUp(self):
        # Create a dummy CaseFilterService with a filter_cases method.
        self.dummy_filter_service = MagicMock(name="CaseFilterService")
        self.report_service = SeverityGroupingReport(self.dummy_filter_service)

    def test_empty_filtered_cases(self):
        """
        When no cases are returned by the filter service,
        the report should show 0 total cases and an empty severity count.
        """
        self.dummy_filter_service.filter_cases.return_value = []
        report = self.report_service.generate_report()
        # Ensure the filter method was called.
        self.dummy_filter_service.filter_cases.assert_called_once()
        self.assertEqual(report["total_cases"], 0)
        self.assertEqual(report["severity_counts"], {})

    def test_all_same_severity(self):
        """
        When all filtered cases have the same severity,
        the report should correctly count the total and group by that severity.
        """
        cases = [
            {"severity": "hospitalisasi"},
            {"severity": "hospitalisasi"},
            {"severity": "hospitalisasi"}
        ]
        self.dummy_filter_service.filter_cases.return_value = cases
        report = self.report_service.generate_report()
        self.dummy_filter_service.filter_cases.assert_called_once()
        self.assertEqual(report["total_cases"], 3)
        self.assertEqual(report["severity_counts"], {"hospitalisasi": 3})

    def test_multiple_severities(self):
        """
        When filtered cases contain multiple severities,
        the report should aggregate counts correctly.
        Note: Cases with None for severity are ignored.
        """
        cases = [
            {"severity": "hospitalisasi"},
            {"severity": "insiden"},
            {"severity": "hospitalisasi"},
            {"severity": "mortalitas"},
            {"severity": "insiden"},
            {"severity": "hospitalisasi"},
            {"severity": None}  # This case should be ignored.
        ]
        self.dummy_filter_service.filter_cases.return_value = cases
        report = self.report_service.generate_report()
        self.dummy_filter_service.filter_cases.assert_called_once()
        self.assertEqual(report["total_cases"], 7)
        self.assertEqual(report["severity_counts"], {
            "hospitalisasi": 3,
            "insiden": 2,
            "mortalitas": 1
        })

class TestAgeGroupingReport(unittest.TestCase):
    def setUp(self):
        """Set up test environment for AgeGroupingReport"""
        self.report_service = AgeGroupingReport()

    def test_empty_cases(self):
        """
        Unhappy path: when no cases are provided,
        the report should show all age groups with 0 count.
        """
        report = self.report_service.generate_report(filtered_cases=None)
        
        # Check all age groups are present with zero counts
        self.assertEqual(report["under_12"], 0)
        self.assertEqual(report["12_25"], 0)
        self.assertEqual(report["26_45"], 0)
        self.assertEqual(report["above_45"], 0)
        
    def test_cases_with_various_ages(self):
        """
        Happy path: when cases with various ages are provided,
        the report should correctly group them into age categories.
        """
        cases = [
            {"id": "1", "age": 8},     # under_12
            {"id": "2", "age": 15},    # 12_25
            {"id": "3", "age": 12},    # 12_25 (boundary)
            {"id": "4", "age": 25},    # 12_25 (boundary)
            {"id": "5", "age": 30},    # 26_45
            {"id": "6", "age": 26},    # 26_45 (boundary)
            {"id": "7", "age": 45},    # 26_45 (boundary)
            {"id": "8", "age": 60}     # above_45
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Check counts for each age group
        self.assertEqual(report["under_12"], 1)
        self.assertEqual(report["12_25"], 3)
        self.assertEqual(report["26_45"], 3)
        self.assertEqual(report["above_45"], 1)
    
    def test_duplicate_case_ids(self):
        """
        Edge case: when duplicate case IDs are present,
        each unique case should only be counted once.
        """
        cases = [
            {"id": "1", "age": 8},     # under_12
            {"id": "2", "age": 15},    # 12_25
            {"id": "1", "age": 8},     # Duplicate of first case - should be ignored
            {"id": "3", "age": 30},    # 26_45
            {"id": "2", "age": 15},    # Duplicate of second case - should be ignored
            {"id": "4", "age": 60}     # above_45
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Check counts for each age group (should only count unique case IDs)
        self.assertEqual(report["under_12"], 1)
        self.assertEqual(report["12_25"], 1)
        self.assertEqual(report["26_45"], 1)
        self.assertEqual(report["above_45"], 1)
    
    def test_missing_age_value(self):
        """
        Edge case: when some cases are missing the age value,
        these cases should be ignored in the count.
        """
        cases = [
            {"id": "1", "age": 8},         # under_12
            {"id": "2"},                   # Missing age - should be ignored
            {"id": "3", "age": None},      # None age - should be ignored
            {"id": "4", "age": 15},        # 12_25
            {"id": "5", "age": 30},        # 26_45
            {"id": "6", "age": 60}         # above_45
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Check counts for each age group
        self.assertEqual(report["under_12"], 1)
        self.assertEqual(report["12_25"], 1)
        self.assertEqual(report["26_45"], 1)
        self.assertEqual(report["above_45"], 1)
    
    def test_boundary_values(self):
        """
        Edge case: testing boundary values for each age group
        to ensure proper classification.
        """
        cases = [
            {"id": "1", "age": 0},      # under_12 (minimum age)
            {"id": "2", "age": 11},     # under_12 (upper boundary)
            {"id": "3", "age": 12},     # 12_25 (lower boundary)
            {"id": "4", "age": 25},     # 12_25 (upper boundary)
            {"id": "5", "age": 26},     # 26_45 (lower boundary)
            {"id": "6", "age": 45},     # 26_45 (upper boundary)
            {"id": "7", "age": 46}      # above_45 (lower boundary)
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Check counts for each age group
        self.assertEqual(report["under_12"], 2)
        self.assertEqual(report["12_25"], 2)
        self.assertEqual(report["26_45"], 2)
        self.assertEqual(report["above_45"], 1)
    
    def test_negative_ages(self):
        """
        Edge case: when negative ages are provided,
        they should still be classified correctly based on the logic.
        """
        cases = [
            {"id": "1", "age": -5}      # Should be under_12
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Check counts for each age group
        self.assertEqual(report["under_12"], 1)
        self.assertEqual(report["12_25"], 0)
        self.assertEqual(report["26_45"], 0)
        self.assertEqual(report["above_45"], 0)
    
    def test_extreme_values(self):
        """
        Edge case: when very large age values are provided,
        they should be classified as above_45.
        """
        cases = [
            {"id": "1", "age": 999}     # Should be above_45
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Check counts for each age group
        self.assertEqual(report["under_12"], 0)
        self.assertEqual(report["12_25"], 0)
        self.assertEqual(report["26_45"], 0)
        self.assertEqual(report["above_45"], 1)

class GenderGroupingReportTestCase(TestCase):
    def setUp(self):
        self.report = GenderGroupingReport()

    def test_generate_report_with_data(self):
        cases = [
            {"id": 1, "gender": "male"},
            {"id": 2, "gender": "female"},
            {"id": 3, "gender": "male"},
        ]
        result = self.report.generate_report(cases)
        self.assertEqual(result, {"male": 2, "female": 1})

    def test_generate_report_with_empty_data(self):
        result = self.report.generate_report([])
        self.assertEqual(result, {"male": 0, "female": 0})

    def test_generate_report_with_invalid_gender(self):
        cases = [
            {"id": 1, "gender": "male"},
            {"id": 2, "gender": "unknown"},
            {"id": 3, "gender": "female"},
        ]
        result = self.report.generate_report(cases)
        self.assertEqual(result, {"male": 1, "female": 1})

    def test_generate_report_with_missing_gender(self):
        """
        Edge case: when some cases are missing the gender field,
        they should be ignored in the count.
        """
        cases = [
            {"id": 1, "gender": "male"},
            {"id": 2},  # Missing gender
            {"id": 3, "gender": None},  # None gender
            {"id": 4, "gender": "female"},
        ]
        result = self.report.generate_report(cases)
        self.assertEqual(result, {"male": 1, "female": 1})

    def test_generate_report_with_mixed_case_gender(self):
        """
        Edge case: gender values with mixed casing (e.g., "Male", "FEMALE")
        should be normalized and counted correctly.
        """
        cases = [
            {"id": 1, "gender": "Male"},
            {"id": 2, "gender": "FEMALE"},
            {"id": 3, "gender": "male"},
            {"id": 4, "gender": "female"},
        ]
        result = self.report.generate_report(cases)
        self.assertEqual(result, {"male": 2, "female": 2})

    def test_generate_report_with_only_invalid_genders(self):
        """
        Edge case: when all cases have invalid gender values,
        the report should return zero counts for both male and female.
        """
        cases = [
            {"id": 1, "gender": "unknown"},
            {"id": 2, "gender": "other"},
            {"id": 3, "gender": None},
        ]
        result = self.report.generate_report(cases)
        self.assertEqual(result, {"male": 0, "female": 0})

    def test_generate_report_with_large_dataset(self):
        """
        Performance test: ensure the report works correctly with a large dataset.
        """
        cases = [{"id": i, "gender": "male" if i % 2 == 0 else "female"} for i in range(1, 10001)]
        result = self.report.generate_report(cases)
        self.assertEqual(result, {"male": 5000, "female": 5000})