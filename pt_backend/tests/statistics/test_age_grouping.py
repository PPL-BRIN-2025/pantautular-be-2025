import unittest

from pt_backend.statistics.reports.age_grouping import AgeGroupingReport


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