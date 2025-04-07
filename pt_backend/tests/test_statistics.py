from django.test import TestCase
from pt_backend.statistics import SeverityGroupingReport
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