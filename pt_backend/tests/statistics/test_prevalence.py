from django.test import TestCase
from datetime import datetime
from unittest.mock import MagicMock, patch

from pt_backend.statistics.reports.prevalence import PrevalenceStatistics


class TestPrevalenceReport(TestCase):
    def setUp(self):
        # dummy repo yang count() bisa kita atur per-test
        self.repo = MagicMock()
        self.report = PrevalenceStatistics(repository=self.repo)

    def test_default_year(self):
        # misal tahun ini: 2024, total_cases=50
        self.repo.get_cases_by_year.return_value.count.return_value = 50
        out = self.report.generate_report()
        self.assertEqual(out["year"], 2024)
        self.assertEqual(out["total_cases"], 50)
        self.assertIsInstance(out["population"], int)
        self.assertIsInstance(out["prevalence"], float)

    def test_with_iso_start_date(self):
        # tetapkan 2022 dan count=100
        self.repo.get_cases_by_year.return_value.count.return_value = 100
        out = self.report.generate_report(start_date="2022-03-15T10:00:00Z")
        self.assertEqual(out["year"], 2022)
        self.assertEqual(out["total_cases"], 100)

    def test_invalid_year_no_population(self):
        # gunakan tahun 2000 yang tidak ada di POPULATION_DATA
        self.repo.get_cases_by_year.return_value.count.return_value = 5
        out = self.report.generate_report(start_date="2000-01-01")
        self.assertEqual(out["year"], 2000)
        self.assertEqual(out["total_cases"], 5)
        self.assertEqual(out["prevalence"], "No Data")

    def test_invalid_date_format(self):
        res = self.report.generate_report(start_date="bad-date")
        self.assertIn("error", res)

    @patch("pt_backend.statistics.reports.prevalence.datetime")
    def test_strptime_called(self, mock_dt):
        # mocking datetime.strptime agar deterministik
        mock_dt.strptime.return_value = datetime(2021, 1, 1)
        self.repo.get_cases_by_year.return_value.count.return_value = 0
        out = self.report.generate_report(start_date="2021-01-01")
        mock_dt.strptime.assert_called_once_with("2021-01-01", "%Y-%m-%d")
        self.assertEqual(out["year"], 2021)