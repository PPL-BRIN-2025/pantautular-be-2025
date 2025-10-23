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
        expected_year = datetime.now().year
        self.repo.get_cases_by_year.return_value.count.return_value = 50
        out = self.report.generate_report()
        self.assertEqual(out["year"], expected_year)
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
        expected_year = datetime.now().year
        res = self.report.generate_report(start_date="bad-date")
        self.assertEqual(res["year"], expected_year)
        self.assertNotIn("error", res)

    def test_uses_filtered_queryset_when_available(self):
        filtered_qs = MagicMock()
        filtered_qs.filter.return_value = filtered_qs
        filtered_qs.count.return_value = 7

        result = self.report.generate_report(filtered_cases=filtered_qs, start_date="2023-01-01")

        filtered_qs.filter.assert_called_once_with(news__date_published__year=2023)
        filtered_qs.count.assert_called_once()
        self.repo.get_cases_by_year.assert_not_called()
        self.assertEqual(result["total_cases"], 7)

    def test_population_fallback_to_latest_known_year(self):
        self.repo.get_cases_by_year.return_value.count.return_value = 10
        result = self.report.generate_report(start_date="2026-01-01")
        self.assertEqual(result["year"], 2026)
        self.assertEqual(result["population"], self.report.POPULATION_DATA[2024])

    def test_date_range_iterable_extracts_start(self):
        self.repo.get_cases_by_year.return_value.count.return_value = 3
        date_range = ("2021-05-01", "2021-05-31")
        result = self.report.generate_report(date_range=date_range)
        self.assertEqual(result["year"], 2021)
        self.repo.get_cases_by_year.assert_called_with(2021)

    @patch("pt_backend.statistics.reports.prevalence.datetime")
    def test_strptime_called(self, mock_dt):
        # mocking datetime.strptime agar deterministik
        mock_dt.strptime.return_value = datetime(2021, 1, 1)
        mock_dt.now.return_value = datetime(2024, 1, 1)
        self.repo.get_cases_by_year.return_value.count.return_value = 0
        out = self.report.generate_report(start_date="2021-01-01")
        mock_dt.strptime.assert_called_once_with("2021-01-01", "%Y-%m-%d")
        self.assertEqual(out["year"], 2021)