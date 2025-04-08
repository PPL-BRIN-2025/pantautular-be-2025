from django.test import TestCase
from django.utils import timezone
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
from ..models import Case, Disease, Location, News
from ..repositories import CaseRepository
from ..statistics import (
    PrevalenceStatistics, 
    StatisticsCoordinator, 
    AgeGroupingReport, 
    GenderGroupingReport, 
    SeverityGroupingReport,
    SeverityDatesCountReport
)
import unittest
import uuid

class BaseStatisticsTestCase(TestCase):
    def setUp(self):
        # Create test disease
        self.disease = Disease.objects.create(
            name="Test Disease",
            level_of_alertness=1
        )
        
        # Create test location
        self.location = Location.objects.create(
            latitude=0.0,
            longitude=0.0,
            city="Test City",
            province="Test Province"
        )
        
        # Create test case
        self.case = Case.objects.create(
            id=uuid.uuid4(),
            gender="Pria",
            age=25,
            city="Test City",
            status="terjangkit",
            severity="hospitalisasi",
            disease=self.disease,
            location=self.location
        )
        
        # Create test news
        self.news = News.objects.create(
            id=uuid.uuid4(),
            portal="Test Portal",
            title="Test News",
            type="Test Type",
            content="Test Content",
            url="https://test.com",
            author="Test Author",
            date_published=timezone.now(),
            case=self.case
        )

class PrevalenceStatisticsTest(BaseStatisticsTestCase):
    def setUp(self):
        super().setUp()
        self.repository = CaseRepository()
        self.statistics = PrevalenceStatistics(self.repository)

    def test_get_prevalence_statistics_default_year(self):
        """Test getting prevalence statistics with default year"""
        result = self.statistics.get_prevalence_statistics()
        
        self.assertEqual(result["year"], 2024)
        self.assertEqual(result["total_cases"], 0)
        self.assertIsInstance(result["population"], int)
        self.assertIsInstance(result["prevalence"], float)

    def test_get_prevalence_statistics_with_start_date(self):
        """Test getting prevalence statistics with a specific start date"""
        # Create a case with a specific year
        specific_date = timezone.make_aware(datetime(2023, 1, 1))
        case_2023 = Case.objects.create(
            id=uuid.uuid4(),
            gender="Pria",
            age=30,
            city="Test City",
            status="terjangkit",
            severity="hospitalisasi",
            disease=self.disease,
            location=self.location
        )
        
        News.objects.create(
            id=uuid.uuid4(),
            portal="Test Portal",
            title="2023 Case",
            type="Test Type",
            content="2023 case content",
            url="https://test.com/2023",
            author="Test Author",
            date_published=specific_date,
            case=case_2023
        )
        
        result = self.statistics.get_prevalence_statistics("2023-01-01")
        
        self.assertEqual(result["year"], 2023)
        self.assertEqual(result["total_cases"], 1)
        self.assertEqual(result["population"], 278696200)
        self.assertIsInstance(result["prevalence"], float)

    def test_get_prevalence_statistics_invalid_year(self):
        """Test getting prevalence statistics with an invalid year (no population data)"""
        result = self.statistics.get_prevalence_statistics("2000-01-01")
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Population data not available for year 2000")

    def test_get_prevalence_statistics_no_cases(self):
        """Test getting prevalence statistics when there are no cases for the year"""
        # Delete all cases
        Case.objects.all().delete()
        
        result = self.statistics.get_prevalence_statistics()
        
        self.assertEqual(result["year"], 2024)
        self.assertEqual(result["total_cases"], 0)
        self.assertIsInstance(result["population"], int)
        self.assertEqual(result["prevalence"], 0.0)
    
    def test_get_prevalence_statistics_invalid_date_format(self):
        """Test getting prevalence statistics with an invalid date format"""
        result = self.statistics.get_prevalence_statistics("invalid-date")
        self.assertIn("error", result)
        
    @patch('pt_backend.statistics.datetime')
    def test_get_prevalence_statistics_with_mocked_date(self, mock_datetime):
        """Test getting prevalence statistics with a mocked date"""
        # Mock the datetime.strptime to return a specific date
        mock_datetime.strptime.return_value = datetime(2023, 1, 1)
        
        result = self.statistics.get_prevalence_statistics("2023-01-01")
        
        # Verify that strptime was called with the correct arguments
        mock_datetime.strptime.assert_called_once_with("2023-01-01", '%Y-%m-%d')
        
        # Verify the result
        self.assertEqual(result["year"], 2023)
        self.assertEqual(result["total_cases"], 0)
        self.assertEqual(result["population"], 278696200)

class StatisticsCoordinatorTest(BaseStatisticsTestCase):
    def setUp(self):
        super().setUp()
        # Create a mock case filter service
        self.mock_case_filter_service = Mock()
        self.mock_case_filter_service.filter_cases.return_value = [
            {
                "id": str(self.case.id),
                "gender": "Pria",
                "age": 25,
                "severity": "hospitalisasi",
                "news__date_published": self.news.date_published
            }
        ]
        
        # Create the coordinator
        self.coordinator = StatisticsCoordinator(self.mock_case_filter_service)
        
    def test_generate_comprehensive_report_with_start_date(self):
        """Test generating a comprehensive report with a start date"""
        result = self.coordinator.generate_comprehensive_report(
            date_range={"start": "2023-01-01", "end": None}
        )
        
        # Verify the result contains all expected statistics
        self.assertIn("prevalence_statistics", result)
        self.assertIn("age_statistics", result)
        self.assertIn("gender_statistics", result)
        self.assertIn("severity_dates_statistics", result)
        
        # Verify that filter_cases was called
        self.mock_case_filter_service.filter_cases.assert_called_once()
        
    def test_generate_comprehensive_report_without_start_date(self):
        """Test generating a comprehensive report without a start date"""
        result = self.coordinator.generate_comprehensive_report()
        
        # Verify the result contains all expected statistics
        self.assertIn("prevalence_statistics", result)
        self.assertIn("age_statistics", result)
        self.assertIn("gender_statistics", result)
        self.assertIn("severity_dates_statistics", result)
        
        # Verify that filter_cases was called
        self.mock_case_filter_service.filter_cases.assert_called_once()
        
    def test_generate_comprehensive_report_with_date_range(self):
        """Test generating a comprehensive report with a date range"""
        result = self.coordinator.generate_comprehensive_report(
            date_range={"start": "2023-01-01", "end": "2023-12-31"}
        )
        
        # Verify the result contains all expected statistics
        self.assertIn("prevalence_statistics", result)
        self.assertIn("age_statistics", result)
        self.assertIn("gender_statistics", result)
        self.assertIn("severity_dates_statistics", result)
        
        # Verify that filter_cases was called with the correct date range
        self.mock_case_filter_service.filter_cases.assert_called_once()
        call_args = self.mock_case_filter_service.filter_cases.call_args[1]
        self.assertIn('date_range', call_args)
        self.assertEqual(call_args['date_range']['start'], "2023-01-01")
        self.assertEqual(call_args['date_range']['end'], "2023-12-31")
        
    def test_generate_comprehensive_report_with_disease_filter(self):
        """Test generating a comprehensive report with a disease filter"""
        result = self.coordinator.generate_comprehensive_report(
            disease=["Test Disease"]
        )
        
        # Verify that filter_cases was called with the correct disease filter
        self.mock_case_filter_service.filter_cases.assert_called_once()
        call_args = self.mock_case_filter_service.filter_cases.call_args[1]
        self.assertIn('disease', call_args)
        self.assertEqual(call_args['disease'], ["Test Disease"])
        
    def test_generate_comprehensive_report_with_location_filter(self):
        """Test generating a comprehensive report with a location filter"""
        result = self.coordinator.generate_comprehensive_report(
            provinces=["Test Province"]
        )
        
        # Verify that filter_cases was called with the correct location filter
        self.mock_case_filter_service.filter_cases.assert_called_once()
        call_args = self.mock_case_filter_service.filter_cases.call_args[1]
        self.assertIn('provinces', call_args)
        self.assertEqual(call_args['provinces'], ["Test Province"])
        
    def test_generate_comprehensive_report_with_portal_filter(self):
        """Test generating a comprehensive report with a portal filter"""
        result = self.coordinator.generate_comprehensive_report(
            portals=["Test Portal"]
        )
        
        # Verify that filter_cases was called with the correct portal filter
        self.mock_case_filter_service.filter_cases.assert_called_once()
        call_args = self.mock_case_filter_service.filter_cases.call_args[1]
        self.assertIn('portals', call_args)
        self.assertEqual(call_args['portals'], ["Test Portal"])
        
    def test_generate_comprehensive_report_with_alertness_filter(self):
        """Test generating a comprehensive report with an alertness filter"""
        result = self.coordinator.generate_comprehensive_report(
            disease_alertness=1
        )
        
        # Verify that filter_cases was called with the correct alertness filter
        self.mock_case_filter_service.filter_cases.assert_called_once()
        call_args = self.mock_case_filter_service.filter_cases.call_args[1]
        self.assertIn('disease_alertness', call_args)
        self.assertEqual(call_args['disease_alertness'], 1)
        
    def test_generate_comprehensive_report_with_multiple_filters(self):
        """Test generating a comprehensive report with multiple filters"""
        result = self.coordinator.generate_comprehensive_report(
            disease=["Test Disease"],
            provinces=["Test Province"],
            portals=["Test Portal"],
            disease_alertness=1,
            date_range={"start": "2023-01-01", "end": "2023-12-31"}
        )
        
        # Verify that filter_cases was called with all the correct filters
        self.mock_case_filter_service.filter_cases.assert_called_once()
        call_args = self.mock_case_filter_service.filter_cases.call_args[1]
        self.assertIn('disease', call_args)
        self.assertIn('provinces', call_args)
        self.assertIn('portals', call_args)
        self.assertIn('disease_alertness', call_args)
        self.assertIn('date_range', call_args)

class TestSeverityGroupingReport(unittest.TestCase):
    def setUp(self):
        # Create a dummy CaseFilterService with a filter_cases method.
        self.dummy_filter_service = MagicMock(name="CaseFilterService")
        self.report_service = SeverityGroupingReport()

    def test_empty_filtered_cases(self):
        """
        When no cases are returned by the filter service,
        the report should show 0 total cases and an empty severity count.
        """
        self.dummy_filter_service.filter_cases.return_value = []
        report = self.report_service.generate_report()
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
        report = self.report_service.generate_report(cases)
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
        report = self.report_service.generate_report(cases)
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

class SeverityDatesCountReportTestCase(TestCase):
    def setUp(self):
        self.report = SeverityDatesCountReport()

    def test_generate_report_with_data(self):
        # Create test data with different severities and dates
        cases = [
            {
                "id": 1, 
                "severity": "hospitalisasi", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 1))
            },
            {
                "id": 2, 
                "severity": "hospitalisasi", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 1))
            },
            {
                "id": 3, 
                "severity": "mortalitas", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 2))
            },
            {
                "id": 4, 
                "severity": "insiden", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 3))
            }
        ]
        
        result = self.report.generate_report(cases)
        
        # Check that the result contains all severities
        self.assertIn("hospitalisasi", result)
        self.assertIn("mortalitas", result)
        self.assertIn("insiden", result)
        
        # Check the counts for each severity and date
        hosp_data = result["hospitalisasi"]
        self.assertEqual(len(hosp_data), 1)
        self.assertEqual(hosp_data[0]["date"], "2023-01-01")
        self.assertEqual(hosp_data[0]["count"], 2)
        
        mort_data = result["mortalitas"]
        self.assertEqual(len(mort_data), 1)
        self.assertEqual(mort_data[0]["date"], "2023-01-02")
        self.assertEqual(mort_data[0]["count"], 1)
        
        incid_data = result["insiden"]
        self.assertEqual(len(incid_data), 1)
        self.assertEqual(incid_data[0]["date"], "2023-01-03")
        self.assertEqual(incid_data[0]["count"], 1)

    def test_generate_report_with_empty_data(self):
        result = self.report.generate_report([])
        self.assertEqual(result, {})

    def test_generate_report_with_none_data(self):
        result = self.report.generate_report(None)
        self.assertEqual(result, {})

    def test_generate_report_with_missing_date(self):
        cases = [
            {
                "id": 1, 
                "severity": "hospitalisasi", 
                "news__date_published": None
            },
            {
                "id": 2, 
                "severity": "hospitalisasi", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 1))
            }
        ]
        
        result = self.report.generate_report(cases)
        
        # Check that only cases with valid dates are included
        self.assertIn("hospitalisasi", result)
        self.assertEqual(result["hospitalisasi"][0]["count"], 1)

    def test_generate_report_with_multiple_dates_per_severity(self):
        cases = [
            {
                "id": 1, 
                "severity": "hospitalisasi", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 1))
            },
            {
                "id": 2, 
                "severity": "hospitalisasi", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 2))
            },
            {
                "id": 3, 
                "severity": "hospitalisasi", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 1))
            }
        ]
        
        result = self.report.generate_report(cases)
        
        # Check that the result contains the correct counts for each date
        self.assertIn("hospitalisasi", result)
        hosp_data = result["hospitalisasi"]
        self.assertEqual(len(hosp_data), 2)
        
        # Sort the data by date to ensure consistent testing
        hosp_data.sort(key=lambda x: x["date"])
        
        self.assertEqual(hosp_data[0]["date"], "2023-01-01")
        self.assertEqual(hosp_data[0]["count"], 2)
        self.assertEqual(hosp_data[1]["date"], "2023-01-02")
        self.assertEqual(hosp_data[1]["count"], 1)