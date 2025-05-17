from unittest import TestCase

from pt_backend.statistics.reports.gender_grouping import GenderGroupingReport


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