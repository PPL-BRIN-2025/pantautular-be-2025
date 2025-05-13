from unittest import TestCase

from pt_backend.statistics.reports.healthcare_news import HealthcareNewsStatisticsReport


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