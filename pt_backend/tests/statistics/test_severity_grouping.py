import unittest
from unittest.mock import MagicMock

from pt_backend.statistics.reports.severity_grouping import SeverityGroupingReport


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
            {"id": 1, "severity": "hospitalisasi"},
            {"id": 2, "severity": "hospitalisasi"},
            {"id": 3, "severity": "hospitalisasi"}
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
            {"id": 1, "severity": "hospitalisasi"},
            {"id": 2, "severity": "insiden"},
            {"id": 3, "severity": "hospitalisasi"},
            {"id": 4, "severity": "mortalitas"},
            {"id": 5, "severity": "insiden"},
            {"id": 6, "severity": "hospitalisasi"},
            {"id": 7, "severity": None}  # This case should be ignored.
        ]
        self.dummy_filter_service.filter_cases.return_value = cases
        report = self.report_service.generate_report(cases)
        self.assertEqual(report["total_cases"], 7)
        self.assertEqual(report["severity_counts"], {
            "hospitalisasi": 3,
            "insiden": 2,
            "mortalitas": 1
        })

    def test_handle_duplicate_case_ids(self):
        """
        Test that the report correctly handles duplicate case IDs by only counting each unique ID once.
        This simulates what happens when filtered_cases has duplicates due to multiple news items.
        """
        cases = [
            {"id": 1, "severity": "hospitalisasi"},
            {"id": 2, "severity": "insiden"},
            {"id": 1, "severity": "hospitalisasi"},  # Duplicate ID
            {"id": 3, "severity": "mortalitas"},
            {"id": 2, "severity": "insiden"},  # Duplicate ID
            {"id": 1, "severity": "hospitalisasi"},  # Duplicate ID
        ]
        report = self.report_service.generate_report(cases)
        self.assertEqual(report["total_cases"], 3)  # Only 3 unique cases
        self.assertEqual(report["severity_counts"], {
            "hospitalisasi": 1,
            "insiden": 1,
            "mortalitas": 1
        })
    
    def test_duplicate_ids_with_different_severities(self):
        """
        Test handling of an edge case where the same case ID appears multiple times 
        with different severity values. Only the first occurrence should be counted.
        """
        cases = [
            {"id": 1, "severity": "hospitalisasi"},
            {"id": 2, "severity": "insiden"},
            {"id": 1, "severity": "mortalitas"},  # Duplicate ID with different severity
            {"id": 3, "severity": "hospitalisasi"}
        ]
        report = self.report_service.generate_report(cases)
        self.assertEqual(report["total_cases"], 3)
        self.assertEqual(report["severity_counts"], {
            "hospitalisasi": 2,
            "insiden": 1
        })

    def test_severity_normalization(self):
        """
        Severities should be normalized (trimmed & lower-cased) before aggregation
        so inconsistent casing in the database does not break charts.
        """
        cases = [
            {"id": 1, "severity": "Hospitalisasi"},
            {"id": 2, "severity": "  INSIDEN  "},
            {"id": 3, "severity": "mortalitas"},
        ]
        report = self.report_service.generate_report(cases)
        self.assertEqual(report["total_cases"], 3)
        self.assertEqual(report["severity_counts"], {
            "hospitalisasi": 1,
            "insiden": 1,
            "mortalitas": 1,
        })

    def test_blank_severity_after_normalization_ignored(self):
        cases = [
            {"id": 1, "severity": "   "},
            {"id": 2, "severity": "Insiden"},
        ]
        report = self.report_service.generate_report(cases)
        self.assertEqual(report["total_cases"], 2)
        self.assertEqual(report["severity_counts"], {"insiden": 1})
