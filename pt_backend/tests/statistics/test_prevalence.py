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

    def test_date_range_dict_extracts_start(self):
        """date_range dict should populate start_date"""
        self.repo.get_cases_by_year.return_value.count.return_value = 11
        result = self.report.generate_report(date_range={"start": "2022-07-01"})
        self.assertEqual(result["year"], 2022)
        self.repo.get_cases_by_year.assert_called_with(2022)

    def test_datetime_start_date_passthrough(self):
        when = datetime(2023, 8, 5)
        self.repo.get_cases_by_year.return_value.count.return_value = 4
        result = self.report.generate_report(start_date=when)
        self.assertEqual(result["year"], 2023)
        self.assertEqual(result["total_cases"], 4)

    def test_infer_year_from_queryset(self):
        mock_case = MagicMock()
        mock_case.news.date_published.year = 2020

        filtered_qs = MagicMock()
        filtered_qs.filter.return_value = filtered_qs
        filtered_qs.order_by.return_value = filtered_qs
        filtered_qs.first.return_value = mock_case
        filtered_qs.count.return_value = 9

        result = self.report.generate_report(filtered_cases=filtered_qs)
        self.assertEqual(result["year"], 2020)
        self.assertEqual(result["total_cases"], 9)
        filtered_qs.filter.assert_called_once_with(news__date_published__year=2020)

    def test_iterable_case_count_branch(self):
        """_count_cases should handle plain iterables."""
        self.repo.get_cases_by_year.return_value = ({"id": i} for i in range(3))
        result = self.report.generate_report(start_date="2022-01-01")
        self.assertEqual(result["total_cases"], 3)

    def test_generate_report_handles_repository_error(self):
        self.repo.get_cases_by_year.side_effect = Exception("db down")
        out = self.report.generate_report(start_date="2022-01-01")
        self.assertIn("error", out)
        self.repo.get_cases_by_year.side_effect = None

    def test_parse_year_with_non_string_value(self):
        """Non string start_date should gracefully fallback."""
        result = self.report.generate_report(start_date=object())
        self.assertIsInstance(result["year"], int)

    def test_infer_year_handles_empty_queryset(self):
        filtered_qs = MagicMock()
        filtered_qs.filter.return_value = filtered_qs
        filtered_qs.order_by.return_value = filtered_qs
        filtered_qs.first.return_value = None
        filtered_qs.count.return_value = 0

        result = self.report.generate_report(filtered_cases=filtered_qs)
        self.assertEqual(result["total_cases"], 0)

    def test_infer_year_handles_missing_news(self):
        mock_case = MagicMock()
        mock_case.news = None

        filtered_qs = MagicMock()
        filtered_qs.filter.return_value = filtered_qs
        filtered_qs.order_by.return_value = filtered_qs
        filtered_qs.first.return_value = mock_case
        filtered_qs.count.return_value = 0

        result = self.report.generate_report(filtered_cases=filtered_qs)
        self.assertEqual(result["total_cases"], 0)

    def test_count_cases_handles_unknown_object(self):
        self.repo.get_cases_by_year.return_value = object()
        result = self.report.generate_report(start_date="2022-01-01")
        self.assertEqual(result["total_cases"], 0)

    def test_string_date_range_is_ignored(self):
        """String date_range should not break iterable branch."""
        self.repo.get_cases_by_year.return_value.count.return_value = 6
        result = self.report.generate_report(date_range="2021-02-01")
        self.assertEqual(result["total_cases"], 6)

    def test_iterable_date_range_without_values(self):
        """Empty iterable should simply fall back to defaults."""
        result = self.report.generate_report(date_range=[])
        self.assertIsInstance(result["year"], int)

    def test_non_iterable_date_range_value(self):
        """Truthy non-iterable should skip iterable branch entirely."""
        result = self.report.generate_report(date_range=5)
        self.assertIsInstance(result["year"], int)
