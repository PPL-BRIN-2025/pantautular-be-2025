from django.test import TestCase
from unittest.mock import MagicMock, Mock

from pt_backend.statistics.coordinator import StatisticsCoordinator
from pt_backend.statistics.reports.prevalence import PrevalenceStatistics


class TestStatisticsCoordinator(TestCase):
    def setUp(self):
        # mock CaseFilterService
        self.mock_filter = MagicMock()
        self.mock_filter.filter_cases.return_value = [{"foo": "bar"}]
        self.coord = StatisticsCoordinator(case_filter_service=self.mock_filter)

    def test_generate_all_reports(self):
        res = self.coord.generate_comprehensive_report()
        # pastikan memanggil filter_cases
        self.mock_filter.filter_cases.assert_called_once()
        # cek semua key strategy muncul
        expected_keys = [
            "prevalence_statistics",
            "age_statistics",
            "gender_statistics",
            "severity_statistics",
            "severity_dates_count_statistics",
            "national_news_statistics",
            "local_portal_statistics",
            "healthcare_news_statistics",
        ]
        for k in expected_keys:
            self.assertIn(k, res)
            self.assertIsInstance(res[k], dict)

    def test_filter_raises_exception(self):
        self.mock_filter.filter_cases.side_effect = Exception("fail")
        res = self.coord.generate_comprehensive_report()
        # kalau filter error, langsung return error di root
        self.assertIn("error", res)

    def test_single_strategy_raises(self):
        # buat salah satu strategy error
        self.coord.strategies["age_statistics"].generate_report = Mock(
            side_effect=Exception("oops")
        )
        out = self.coord.generate_comprehensive_report()
        # pastikan hanya age_statistics yang berisi error
        self.assertIn("error", out["age_statistics"])
        # strategy lain tetap ada
        self.assertIn("gender_statistics", out)
        self.assertNotIn("error", out.get("gender_statistics", {}))
    
    def test_no_filter_service_uses_empty_filtered_list(self):
        """Jika case_filter_service None, maka filtered_cases = []"""
        # buat coordinator tanpa filter service
        coord = StatisticsCoordinator(case_filter_service=None)
        # spy pada salah satu strategy untuk menangkap argumen
        strat = coord.strategies["age_statistics"]
        captured = []
        def fake_report(filtered_cases=None):
            captured.append(filtered_cases)
            return {"ok": True}

        strat.generate_report = fake_report

        out = coord.generate_comprehensive_report()
        # branch else harus mengeksekusi generate_report dengan []
        self.assertIn("age_statistics", out)
        self.assertEqual(captured, [[]])
        self.assertEqual(out["age_statistics"], {"ok": True})

    def test_date_range_dict_sets_start_date(self):
        """Pastikan date_range dict mengisi start_date untuk prevalence strategy."""
        captured_kwargs = {}

        class DummyPrevalence(PrevalenceStatistics):
            def generate_report(self, **kwargs):
                captured_kwargs.update(kwargs)
                return {"ok": True}

        coord = StatisticsCoordinator(case_filter_service=self.mock_filter)
        coord.strategies["prevalence_statistics"] = DummyPrevalence(repository=MagicMock())

        filters = {"date_range": {"start": "2023-04-01"}}
        result = coord.generate_comprehensive_report(**filters)

        self.assertEqual(result["prevalence_statistics"], {"ok": True})
        self.assertEqual(captured_kwargs["start_date"], "2023-04-01")
