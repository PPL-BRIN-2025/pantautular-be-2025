from django.test import TestCase
from pt_backend.statistics import AgeGroupingReport, GenderGroupingReport, LocalPortalStatisticsReport, NationalNewsStatisticsReport, SeverityGroupingReport
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

class TestNationalNewsStatisticsReport(unittest.TestCase):
    def setUp(self):
        """Set up test environment for NationalNewsStatisticsReport"""
        self.report_service = NationalNewsStatisticsReport()
        
        # Define common test data to reuse
        self.sample_national_cases = [
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
        
        # Add non-national cases for mixed tests
        self.mixed_cases = self.sample_national_cases + [
            {
                "id": "5",
                "news__portal": "detik.com",
                "news__type": "Regional",
                "disease__name": "COVID-19"
            },
            {
                "id": "6",
                "news__portal": "kompas.com",
                "news__type": "International",
                "disease__name": "Dengue"
            }
        ]
        
        # Cases with missing data
        self.edge_cases = [
            # Valid case
            {
                "id": "1",
                "news__portal": "kompas.com",
                "news__type": "Nasional",
                "disease__name": "COVID-19"
            },
            # Missing portal
            {
                "id": "2",
                "news__portal": None,
                "news__type": "Nasional",
                "disease__name": "COVID-19"
            },
            # Missing news type
            {
                "id": "3",
                "news__portal": "kompas.com",
                "news__type": None,
                "disease__name": "Dengue"
            },
            # Missing both portal and news type
            {
                "id": "4",
                "disease__name": "Malaria"
            },
            # Missing disease
            {
                "id": "5",
                "news__portal": "detik.com",
                "news__type": "Nasional",
                "disease__name": None
            }
        ]

    def test_empty_cases(self):
        """Test behavior with empty datasets"""
        # Test with None
        report = self.report_service.generate_report(filtered_cases=None)
        self.assertEqual(report["top_national"], [])
        self.assertEqual(report["all_national"], [])
        
        # Test with empty list
        report = self.report_service.generate_report(filtered_cases=[])
        self.assertEqual(report["top_national"], [])
        self.assertEqual(report["all_national"], [])

    def test_national_news_counts(self):
        """Test correct counting of national news by portal"""
        report = self.report_service.generate_report(filtered_cases=self.sample_national_cases)
        
        # Validate top_national
        self.assertEqual(len(report["top_national"]), 3)  # 3 unique portals
        
        # Check sorting (should be kompas.com first with 2 news)
        self.assertEqual(report["top_national"][0]["portal"], "kompas.com")
        self.assertEqual(report["top_national"][0]["count"], 2)
        
        # Verify remaining portals have correct counts
        portal_counts = {item["portal"]: item["count"] for item in report["top_national"]}
        self.assertEqual(portal_counts, {"kompas.com": 2, "detik.com": 1, "cnn.com": 1})

    def test_disease_counting(self):
        """Test accurate counting of unique diseases per portal"""
        report = self.report_service.generate_report(filtered_cases=self.sample_national_cases)
        
        # Extract portal data from all_national for easier testing
        portal_data = {item["portal"]: (item["news_count"], item["disease_count"]) 
                      for item in report["all_national"]}
        
        # Verify each portal has correct news and disease counts
        self.assertEqual(portal_data["kompas.com"], (2, 2))  # 2 news, 2 diseases
        self.assertEqual(portal_data["detik.com"], (1, 1))   # 1 news, 1 disease
        self.assertEqual(portal_data["cnn.com"], (1, 1))     # 1 news, 1 disease

    def test_filtering_non_national_news(self):
        """Test that only 'Nasional' type news are included"""
        report = self.report_service.generate_report(filtered_cases=self.mixed_cases)
        
        # Should only have the same results as with just national news
        portal_counts = {item["portal"]: item["count"] for item in report["top_national"]}
        self.assertEqual(portal_counts, {"kompas.com": 2, "detik.com": 1, "cnn.com": 1})
        
        # Ensure non-national news portals aren't included or miscounted
        for item in report["all_national"]:
            if item["portal"] == "kompas.com":
                self.assertEqual(item["news_count"], 2)  # Only the 2 national ones
            elif item["portal"] == "detik.com":
                self.assertEqual(item["news_count"], 1)  # Only the 1 national one

    def test_edge_cases(self):
        """Test handling of missing data fields"""
        report = self.report_service.generate_report(filtered_cases=self.edge_cases)
        
        # Only kompas and detik should appear (with valid news__type = "Nasional")
        portals = [item["portal"] for item in report["top_national"]]
        self.assertIn("kompas.com", portals)
        self.assertIn("detik.com", portals)
        
        # Extract for easier testing
        portal_data = {item["portal"]: (item["news_count"], item["disease_count"]) 
                      for item in report["all_national"]}
        
        # kompas has 1 valid national news with disease
        self.assertEqual(portal_data["kompas.com"], (1, 1))
        
        # detik has 1 valid national news but missing disease
        self.assertEqual(portal_data["detik.com"], (1, 0))

    def test_sorting_by_count(self):
        """Test proper sorting of results by news count"""
        # Create data with predictable sorting
        cases = [
            {"id": "1", "news__portal": "high", "news__type": "Nasional", "disease__name": "D1"},
            {"id": "2", "news__portal": "high", "news__type": "Nasional", "disease__name": "D2"},
            {"id": "3", "news__portal": "high", "news__type": "Nasional", "disease__name": "D3"},
            {"id": "4", "news__portal": "medium", "news__type": "Nasional", "disease__name": "D1"},
            {"id": "5", "news__portal": "medium", "news__type": "Nasional", "disease__name": "D2"},
            {"id": "6", "news__portal": "low", "news__type": "Nasional", "disease__name": "D1"}
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Verify correct sorting order
        self.assertEqual([item["portal"] for item in report["top_national"]], 
                         ["high", "medium", "low"])
        
        # Verify counts
        self.assertEqual([item["count"] for item in report["top_national"]], 
                         [3, 2, 1])

from django.test import TestCase
from pt_backend.statistics import HealthcareNewsStatisticsReport

class TestHealthcareNewsStatisticsReport(TestCase):
    def setUp(self):
        """Set up test environment for HealthcareNewsStatisticsReport"""
        self.report_service = HealthcareNewsStatisticsReport()

    def test_empty_cases(self):
        """Test behavior with empty datasets"""
        report = self.report_service.generate_report(filtered_cases=None)
        self.assertEqual(report, {"top_healthcare": [], "all_healthcare": []})

    def test_healthcare_news_counts(self):
        """Test correct counting of healthcare news by portal"""
        cases = [
            {"id": "1", "news__portal": "kompas.com", "news__type": "Kesehatan", "disease__name": "COVID-19"},
            {"id": "2", "news__portal": "detik.com", "news__type": "Kesehatan", "disease__name": "COVID-19"},
            {"id": "3", "news__portal": "kompas.com", "news__type": "Kesehatan", "disease__name": "Dengue"},
            {"id": "4", "news__portal": "cnn.com", "news__type": "Kesehatan", "disease__name": "Malaria"}
        ]
        report = self.report_service.generate_report(filtered_cases=cases)

        # Validate top_healthcare
        self.assertEqual(len(report["top_healthcare"]), 3)  # 3 unique portals
        self.assertEqual(report["top_healthcare"][0]["portal"], "kompas.com")  # Most news
        self.assertEqual(report["top_healthcare"][0]["count"], 2)

        # Validate all_healthcare
        portal_data = {item["portal"]: (item["news_count"], item["disease_count"]) for item in report["all_healthcare"]}
        self.assertEqual(portal_data["kompas.com"], (2, 2))  # 2 news, 2 diseases
        self.assertEqual(portal_data["detik.com"], (1, 1))   # 1 news, 1 disease
        self.assertEqual(portal_data["cnn.com"], (1, 1))     # 1 news, 1 disease

    def test_edge_cases(self):
        """Test handling of missing or inconsistent data fields"""
        cases = [
            {"id": "1", "news__portal": "kompas.com", "news__type": "Kesehatan", "disease__name": "COVID-19"},
            {"id": "2", "news__portal": None, "news__type": "Kesehatan", "disease__name": "Dengue"},
            {"id": "3", "news__portal": "cnn.com", "news__type": None, "disease__name": "Malaria"},
            {"id": "4", "news__portal": "detik.com", "news__type": "kesehatan", "disease__name": None}
        ]
        report = self.report_service.generate_report(filtered_cases=cases)

        # Validate top_healthcare
        self.assertEqual(len(report["top_healthcare"]), 2)  # Only valid portals
        self.assertIn("kompas.com", [item["portal"] for item in report["top_healthcare"]])
        self.assertIn("detik.com", [item["portal"] for item in report["top_healthcare"]])

        # Validate all_healthcare
        portal_data = {item["portal"]: (item["news_count"], item["disease_count"]) for item in report["all_healthcare"]}
        self.assertEqual(portal_data["kompas.com"], (1, 1))  # 1 news, 1 disease
        self.assertEqual(portal_data["detik.com"], (1, 0))   # 1 news, 0 diseases

class TestLocalPortalStatisticsReport(unittest.TestCase):
    def setUp(self):
        """Set up test environment for LocalPortalStatisticsReport"""
        self.report_service = LocalPortalStatisticsReport()
    
    def test_empty_cases(self):
        """
        Unhappy path: when no cases are provided,
        the report should return an empty dictionary.
        """
        # Test with None
        report = self.report_service.generate_report(filtered_cases=None)
        self.assertEqual(report, {})
        
        # Test with empty list
        report = self.report_service.generate_report(filtered_cases=[])
        self.assertEqual(report, {})
    
    def test_happy_path_multiple_portals(self):
        """
        Happy path: when cases with different local portals and diseases are provided,
        the report should correctly count news and unique diseases per portal.
        """
        cases = [
            {"news__type": "Lokal", "news__portal": "kompas.com", "disease__name": "Malaria"},
            {"news__type": "Lokal", "news__portal": "kompas.com", "disease__name": "Dengue"},
            {"news__type": "Lokal", "news__portal": "kompas.com", "disease__name": "Malaria"},  # Duplicate disease
            {"news__type": "Lokal", "news__portal": "detik.com", "disease__name": "Dengue"},
            {"news__type": "Lokal", "news__portal": "detik.com", "disease__name": "COVID-19"},
            {"news__type": "Lokal", "news__portal": "cnn.com", "disease__name": "Malaria"}
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        self.assertEqual(len(report), 3)  # 3 different portals
        
        # Check kompas.com stats
        self.assertEqual(report["kompas.com"]["news_count"], 3)
        self.assertEqual(report["kompas.com"]["disease_count"], 2)  # Only Malaria and Dengue (unique)
        
        # Check detik.com stats
        self.assertEqual(report["detik.com"]["news_count"], 2)
        self.assertEqual(report["detik.com"]["disease_count"], 2)  # Dengue and COVID-19
        
        # Check cnn.com stats
        self.assertEqual(report["cnn.com"]["news_count"], 1)
        self.assertEqual(report["cnn.com"]["disease_count"], 1)  # Only Malaria
    
    def test_non_local_news_ignored(self):
        """
        Edge case: when cases with non-local news are provided,
        they should be ignored in the report.
        """
        cases = [
            {"news__type": "Lokal", "news__portal": "kompas.com", "disease__name": "Malaria"},
            {"news__type": "International", "news__portal": "bbc.com", "disease__name": "COVID-19"},
            {"news__type": "National", "news__portal": "cnn.com", "disease__name": "Dengue"}
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        self.assertEqual(len(report), 1)  # Only kompas.com is local
        self.assertNotIn("bbc.com", report)
        self.assertNotIn("cnn.com", report)
        
        # Check kompas.com stats
        self.assertEqual(report["kompas.com"]["news_count"], 1)
        self.assertEqual(report["kompas.com"]["disease_count"], 1)
    
    def test_missing_fields(self):
        """
        Edge case: when cases with missing fields are provided,
        they should be handled gracefully without errors.
        """
        cases = [
            {"news__type": "Lokal", "news__portal": "kompas.com", "disease__name": "Malaria"},
            {"news__type": "Lokal", "disease__name": "Dengue"},  # Missing news__portal
            {"news__type": "Lokal", "news__portal": "detik.com"},  # Missing disease__name
            {"news__portal": "cnn.com", "disease__name": "COVID-19"},  # Missing news__type
            {}  # Empty case
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        # Only kompas.com should be counted (others have missing critical fields)
        self.assertEqual(len(report), 1)
        
        # Check kompas.com stats
        self.assertEqual(report["kompas.com"]["news_count"], 1)
        self.assertEqual(report["kompas.com"]["disease_count"], 1)
    
    def test_none_values(self):
        """
        Edge case: when cases with None values for key fields are provided,
        they should be handled gracefully.
        """
        cases = [
            {"news__type": "Lokal", "news__portal": None, "disease__name": "Malaria"},
            {"news__type": "Lokal", "news__portal": "detik.com", "disease__name": None}
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)

        self.assertEqual(len(report), 0)