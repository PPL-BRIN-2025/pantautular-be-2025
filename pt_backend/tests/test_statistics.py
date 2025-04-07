from django.test import TestCase
from pt_backend.statistics import AgeGroupingReport, SeverityGroupingReport
from unittest.mock import MagicMock, call
import unittest

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

class TestSeverityDatesCountReport(unittest.TestCase):
    def setUp(self):
        """Set up test environment for SeverityDatesCountReport"""
        from pt_backend.statistics import SeverityDatesCountReport
        self.report_service = SeverityDatesCountReport()
    
    def test_empty_cases(self):
        """
        Unhappy path: when no cases are provided,
        the report should return an empty dictionary.
        """
        report = self.report_service.generate_report(filtered_cases=None)
        self.assertEqual(report, {})
        
        report = self.report_service.generate_report(filtered_cases=[])
        self.assertEqual(report, {})
    
    def test_various_severity_and_dates(self):
        """
        Happy path: when cases with various severities and dates are provided,
        the report should correctly group them.
        """
        from datetime import datetime
        
        cases = [
            {"severity": "hospitalisasi", "news__date_published": datetime(2023, 1, 1)},
            {"severity": "hospitalisasi", "news__date_published": datetime(2023, 1, 1)},
            {"severity": "hospitalisasi", "news__date_published": datetime(2023, 1, 2)},
            {"severity": "insiden", "news__date_published": datetime(2023, 1, 1)},
            {"severity": "insiden", "news__date_published": datetime(2023, 1, 3)},
            {"severity": "mortalitas", "news__date_published": datetime(2023, 1, 2)}
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Check structure and content of the report
        self.assertIn("hospitalisasi", report)
        self.assertIn("insiden", report)
        self.assertIn("mortalitas", report)
        
        # Check hospitalisasi counts by date
        hospitalisasi_dates = {item["date"]: item["count"] for item in report["hospitalisasi"]}
        self.assertEqual(hospitalisasi_dates["2023-01-01"], 2)
        self.assertEqual(hospitalisasi_dates["2023-01-02"], 1)
        
        # Check insiden counts by date
        insiden_dates = {item["date"]: item["count"] for item in report["insiden"]}
        self.assertEqual(insiden_dates["2023-01-01"], 1)
        self.assertEqual(insiden_dates["2023-01-03"], 1)
        
        # Check mortalitas counts by date
        mortalitas_dates = {item["date"]: item["count"] for item in report["mortalitas"]}
        self.assertEqual(mortalitas_dates["2023-01-02"], 1)
    
    def test_missing_severity_or_date(self):
        """
        Edge case: when some cases are missing severity or date published,
        these cases should be handled gracefully.
        """
        from datetime import datetime
        
        cases = [
            {"severity": "hospitalisasi", "news__date_published": datetime(2023, 1, 1)},
            {"severity": None, "news__date_published": datetime(2023, 1, 1)},  # Missing severity value
            {"news__date_published": datetime(2023, 1, 2)},  # Missing severity key
            {"severity": "insiden"}  # Missing news__date_published key
        ]
        
        # Using try-except to ensure the test doesn't fail due to missing keys
        try:
            report = self.report_service.generate_report(filtered_cases=cases)
            
            # Check that valid case is included
            self.assertIn("hospitalisasi", report)
            hospitalisasi_dates = {item["date"]: item["count"] for item in report["hospitalisasi"]}
            self.assertEqual(hospitalisasi_dates["2023-01-01"], 1)
            
            # Check that None severity is included if present
            if None in report:
                none_dates = {item["date"]: item["count"] for item in report[None]}
                self.assertEqual(none_dates["2023-01-01"], 1)
        except Exception as e:
            self.fail(f"Test failed with exception: {e}")
    
    def test_same_severity_different_dates(self):
        """
        Edge case: when all cases have the same severity but different dates,
        they should be correctly grouped by date.
        """
        from datetime import datetime
        
        cases = [
            {"severity": "hospitalisasi", "news__date_published": datetime(2023, 1, 1)},
            {"severity": "hospitalisasi", "news__date_published": datetime(2023, 1, 2)},
            {"severity": "hospitalisasi", "news__date_published": datetime(2023, 1, 3)},
            {"severity": "hospitalisasi", "news__date_published": datetime(2023, 1, 1)}  # Duplicate date
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Check that only hospitalisasi severity is present
        self.assertEqual(list(report.keys()), ["hospitalisasi"])
        
        # Check counts by date
        hospitalisasi_dates = {item["date"]: item["count"] for item in report["hospitalisasi"]}
        self.assertEqual(hospitalisasi_dates["2023-01-01"], 2)
        self.assertEqual(hospitalisasi_dates["2023-01-02"], 1)
        self.assertEqual(hospitalisasi_dates["2023-01-03"], 1)
    
    def test_different_severity_same_date(self):
        """
        Edge case: when cases have different severities but the same date,
        they should be correctly grouped by severity.
        """
        from datetime import datetime
        
        cases = [
            {"severity": "hospitalisasi", "news__date_published": datetime(2023, 1, 1)},
            {"severity": "insiden", "news__date_published": datetime(2023, 1, 1)},
            {"severity": "mortalitas", "news__date_published": datetime(2023, 1, 1)},
            {"severity": "hospitalisasi", "news__date_published": datetime(2023, 1, 1)}  # Duplicate severity
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Check that all severities are present
        self.assertIn("hospitalisasi", report)
        self.assertIn("insiden", report)
        self.assertIn("mortalitas", report)
        
        # Check counts for each severity
        hospitalisasi_dates = {item["date"]: item["count"] for item in report["hospitalisasi"]}
        insiden_dates = {item["date"]: item["count"] for item in report["insiden"]}
        mortalitas_dates = {item["date"]: item["count"] for item in report["mortalitas"]}
        
        self.assertEqual(hospitalisasi_dates["2023-01-01"], 2)
        self.assertEqual(insiden_dates["2023-01-01"], 1)
        self.assertEqual(mortalitas_dates["2023-01-01"], 1)