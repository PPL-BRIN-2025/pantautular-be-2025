from django.test import TestCase
from pt_backend.statistics import AgeGroupingReport, NationalNewsStatisticsReport, SeverityGroupingReport
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

class TestNationalNewsStatisticsReport(unittest.TestCase):
    def setUp(self):
        """Set up test environment for NationalNewsStatisticsReport"""
        self.report_service = NationalNewsStatisticsReport()

    def test_empty_cases(self):
        """
        Unhappy path: when no cases are provided,
        the report should return empty lists.
        """
        # Test with None
        report = self.report_service.generate_report(filtered_cases=None)
        self.assertEqual(report["top_national"], [])
        self.assertEqual(report["all_national"], [])
        
        # Test with empty list
        report = self.report_service.generate_report(filtered_cases=[])
        self.assertEqual(report["top_national"], [])
        self.assertEqual(report["all_national"], [])

    def test_cases_with_national_news(self):
        """
        Happy path: when cases with national news are provided,
        the report should correctly count them by portal.
        """
        cases = [
            {
                "id": "1",
                "news__portal": "kompas.com",
                "news__type": "Nasional",
                "disease__name": "COVID-19"
            },
            {
                "id": "2",
                "news__portal": "detik.com",
                "news__type": "Nasional",
                "disease__name": "COVID-19"
            },
            {
                "id": "3",
                "news__portal": "kompas.com",
                "news__type": "Nasional",
                "disease__name": "Dengue"
            },
            {
                "id": "4",
                "news__portal": "cnn.com",
                "news__type": "Nasional",
                "disease__name": "Malaria"
            }
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Check top_national format and sorting
        self.assertEqual(len(report["top_national"]), 3)  # 3 unique portals
        self.assertEqual(report["top_national"][0]["portal"], "kompas.com")
        self.assertEqual(report["top_national"][0]["count"], 2)  # kompas has 2 news
        
        # Check all_national format and content
        self.assertEqual(len(report["all_national"]), 3)  # 3 unique portals
        
        # Find kompas.com entry
        kompas_entry = next(entry for entry in report["all_national"] if entry["portal"] == "kompas.com")
        self.assertEqual(kompas_entry["news_count"], 2)  # 2 news articles
        self.assertEqual(kompas_entry["disease_count"], 2)  # 2 unique diseases (COVID-19, Dengue)
        
        # Find detik.com entry
        detik_entry = next(entry for entry in report["all_national"] if entry["portal"] == "detik.com")
        self.assertEqual(detik_entry["news_count"], 1)  # 1 news article
        self.assertEqual(detik_entry["disease_count"], 1)  # 1 unique disease (COVID-19)
        
        # Find cnn.com entry
        cnn_entry = next(entry for entry in report["all_national"] if entry["portal"] == "cnn.com")
        self.assertEqual(cnn_entry["news_count"], 1)  # 1 news article
        self.assertEqual(cnn_entry["disease_count"], 1)  # 1 unique disease (Malaria)

    def test_filtering_non_national_news(self):
        """
        Edge case: when cases include both national and non-national news,
        only the national news should be counted.
        """
        cases = [
            {
                "id": "1",
                "news__portal": "kompas.com",
                "news__type": "Nasional",
                "disease__name": "COVID-19"
            },
            {
                "id": "2",
                "news__portal": "detik.com",
                "news__type": "Regional",  # Not national
                "disease__name": "COVID-19"
            },
            {
                "id": "3",
                "news__portal": "kompas.com",
                "news__type": "International",  # Not national
                "disease__name": "Dengue"
            },
            {
                "id": "4",
                "news__portal": "cnn.com",
                "news__type": "Nasional",
                "disease__name": "Malaria"
            }
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Only 2 national news should be counted (from kompas.com and cnn.com)
        self.assertEqual(len(report["top_national"]), 2)
        
        # Check portals in top_national - only kompas.com and cnn.com should be there (both with 1 news)
        portals = [item["portal"] for item in report["top_national"]]
        self.assertIn("kompas.com", portals)
        self.assertIn("cnn.com", portals)
        self.assertNotIn("detik.com", portals)  # Should not be included

    def test_missing_portal_or_news_type(self):
        """
        Edge case: when cases are missing portal or news_type,
        they should be handled gracefully.
        """
        cases = [
            {
                "id": "1",
                "news__portal": "kompas.com",
                "news__type": "Nasional",
                "disease__name": "COVID-19"
            },
            {
                "id": "2",
                "news__portal": None,  # Missing portal
                "news__type": "Nasional",
                "disease__name": "COVID-19"
            },
            {
                "id": "3",
                "news__portal": "kompas.com",
                "news__type": None,  # Missing news type
                "disease__name": "Dengue"
            },
            {
                "id": "4",  # Missing both portal and news type
                "disease__name": "Malaria"
            }
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Only 1 valid national news (kompas.com)
        self.assertEqual(len(report["top_national"]), 1)
        self.assertEqual(report["top_national"][0]["portal"], "kompas.com")
        self.assertEqual(report["top_national"][0]["count"], 1)

    def test_missing_disease_name(self):
        """
        Edge case: when cases are missing disease name,
        they should still be counted but with zero disease count.
        """
        cases = [
            {
                "id": "1",
                "news__portal": "kompas.com",
                "news__type": "Nasional",
                "disease__name": "COVID-19"
            },
            {
                "id": "2",
                "news__portal": "kompas.com",
                "news__type": "Nasional",
                "disease__name": None  # Missing disease
            },
            {
                "id": "3",
                "news__portal": "kompas.com",
                "news__type": "Nasional"
                # Missing disease key entirely
            }
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # kompas.com should have 3 news but only 1 disease
        self.assertEqual(len(report["top_national"]), 1)
        self.assertEqual(report["top_national"][0]["portal"], "kompas.com")
        self.assertEqual(report["top_national"][0]["count"], 3)
        
        self.assertEqual(report["all_national"][0]["news_count"], 3)
        self.assertEqual(report["all_national"][0]["disease_count"], 1)

    def test_sorting_by_count(self):
        """
        Edge case: verify that results are properly sorted by news count.
        """
        cases = [
            {
                "id": "1",
                "news__portal": "low-count.com",
                "news__type": "Nasional",
                "disease__name": "Disease1"
            },
            {
                "id": "2",
                "news__portal": "high-count.com",
                "news__type": "Nasional",
                "disease__name": "Disease1"
            },
            {
                "id": "3",
                "news__portal": "mid-count.com",
                "news__type": "Nasional",
                "disease__name": "Disease2"
            },
            {
                "id": "4",
                "news__portal": "high-count.com",
                "news__type": "Nasional",
                "disease__name": "Disease2"
            },
            {
                "id": "5",
                "news__portal": "high-count.com",
                "news__type": "Nasional",
                "disease__name": "Disease3"
            },
            {
                "id": "6",
                "news__portal": "mid-count.com",
                "news__type": "Nasional",
                "disease__name": "Disease1"
            }
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Should be sorted: high-count (3), mid-count (2), low-count (1)
        self.assertEqual(report["top_national"][0]["portal"], "high-count.com")
        self.assertEqual(report["top_national"][0]["count"], 3)
        
        self.assertEqual(report["top_national"][1]["portal"], "mid-count.com")
        self.assertEqual(report["top_national"][1]["count"], 2)
        
        self.assertEqual(report["top_national"][2]["portal"], "low-count.com")
        self.assertEqual(report["top_national"][2]["count"], 1)