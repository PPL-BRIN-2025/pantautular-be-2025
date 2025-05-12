import unittest

from pt_backend.statistics.reports.local_portal import LocalPortalStatisticsReport


class TestLocalPortalStatisticsReport(unittest.TestCase):
    def setUp(self):
        """Set up test environment for LocalPortalStatisticsReport"""
        self.report_service = LocalPortalStatisticsReport()
        
        # Define common test data to reuse
        self.sample_local_cases = [
            {
                "id": "1",
                "news__portal": "tribun.com",
                "news__type": "Lokal",
                "disease__name": "COVID-19"
            },
            {
                "id": "2",
                "news__portal": "jawapos.com",
                "news__type": "Lokal",
                "disease__name": "COVID-19"
            },
            {
                "id": "3",
                "news__portal": "tribun.com",
                "news__type": "Lokal",
                "disease__name": "Dengue"
            },
            {
                "id": "4",
                "news__portal": "suarasurabaya.com",
                "news__type": "Lokal",
                "disease__name": "Malaria"
            }
        ]
        
        # Add non-local cases for mixed tests
        self.mixed_cases = self.sample_local_cases + [
            {
                "id": "5",
                "news__portal": "jawapos.com",
                "news__type": "Nasional",
                "disease__name": "COVID-19"
            },
            {
                "id": "6",
                "news__portal": "tribun.com",
                "news__type": "Kesehatan",
                "disease__name": "Dengue"
            }
        ]
        
        # Cases with missing data
        self.edge_cases = [
            # Valid case
            {
                "id": "1",
                "news__portal": "tribun.com",
                "news__type": "Lokal",
                "disease__name": "COVID-19"
            },
            # Missing portal
            {
                "id": "2",
                "news__portal": None,
                "news__type": "Lokal",
                "disease__name": "COVID-19"
            },
            # Missing news type
            {
                "id": "3",
                "news__portal": "tribun.com",
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
                "news__portal": "jawapos.com",
                "news__type": "Lokal",
                "disease__name": None
            }
        ]

    def test_empty_cases(self):
        """Test behavior with empty datasets"""
        # Test with None
        report = self.report_service.generate_report(filtered_cases=None)
        self.assertEqual(report["top_local"], [])
        self.assertEqual(report["all_local"], [])
        
        # Test with empty list
        report = self.report_service.generate_report(filtered_cases=[])
        self.assertEqual(report["top_local"], [])
        self.assertEqual(report["all_local"], [])

    def test_local_news_counts(self):
        """Test correct counting of local news by portal"""
        report = self.report_service.generate_report(filtered_cases=self.sample_local_cases)
        
        # Validate top_local
        self.assertEqual(len(report["top_local"]), 3)  # 3 unique portals
        
        # Check sorting (should be tribun.com first with 2 news)
        self.assertEqual(report["top_local"][0]["portal"], "tribun.com")
        self.assertEqual(report["top_local"][0]["count"], 2)
        
        # Verify remaining portals have correct counts
        portal_counts = {item["portal"]: item["count"] for item in report["top_local"]}
        self.assertEqual(portal_counts, {"tribun.com": 2, "jawapos.com": 1, "suarasurabaya.com": 1})

    def test_disease_counting(self):
        """Test accurate counting of unique diseases per portal"""
        report = self.report_service.generate_report(filtered_cases=self.sample_local_cases)
        
        # Extract portal data from all_local for easier testing
        portal_data = {item["portal"]: (item["news_count"], item["disease_count"]) 
                      for item in report["all_local"]}
        
        # Verify each portal has correct news and disease counts
        self.assertEqual(portal_data["tribun.com"], (2, 2))  # 2 news, 2 diseases
        self.assertEqual(portal_data["jawapos.com"], (1, 1))   # 1 news, 1 disease
        self.assertEqual(portal_data["suarasurabaya.com"], (1, 1))     # 1 news, 1 disease

    def test_filtering_non_local_news(self):
        """Test that only 'Lokal' type news are included"""
        report = self.report_service.generate_report(filtered_cases=self.mixed_cases)
        
        # Should only have the same results as with just local news
        portal_counts = {item["portal"]: item["count"] for item in report["top_local"]}
        self.assertEqual(portal_counts, {"tribun.com": 2, "jawapos.com": 1, "suarasurabaya.com": 1})
        
        # Ensure non-local news portals aren't included or miscounted
        for item in report["all_local"]:
            if item["portal"] == "tribun.com":
                self.assertEqual(item["news_count"], 2)  # Only the 2 local ones
            elif item["portal"] == "jawapos.com":
                self.assertEqual(item["news_count"], 1)  # Only the 1 local one

    def test_edge_cases(self):
        """Test handling of missing data fields"""
        report = self.report_service.generate_report(filtered_cases=self.edge_cases)
        
        # Only tribun and jawapos should appear (with valid news__type = "Lokal")
        portals = [item["portal"] for item in report["top_local"]]
        self.assertIn("tribun.com", portals)
        self.assertIn("jawapos.com", portals)
        
        # Extract for easier testing
        portal_data = {item["portal"]: (item["news_count"], item["disease_count"]) 
                      for item in report["all_local"]}
        
        # tribun has 1 valid local news with disease
        self.assertEqual(portal_data["tribun.com"], (1, 1))
        
        # jawapos has 1 valid local news but missing disease
        self.assertEqual(portal_data["jawapos.com"], (1, 0))

    def test_sorting_by_count(self):
        """Test proper sorting of results by news count"""
        # Create data with predictable sorting
        cases = [
            {"id": "1", "news__portal": "high", "news__type": "Lokal", "disease__name": "D1"},
            {"id": "2", "news__portal": "high", "news__type": "Lokal", "disease__name": "D2"},
            {"id": "3", "news__portal": "high", "news__type": "Lokal", "disease__name": "D3"},
            {"id": "4", "news__portal": "medium", "news__type": "Lokal", "disease__name": "D1"},
            {"id": "5", "news__portal": "medium", "news__type": "Lokal", "disease__name": "D2"},
            {"id": "6", "news__portal": "low", "news__type": "Lokal", "disease__name": "D1"}
        ]
        
        report = self.report_service.generate_report(filtered_cases=cases)
        
        # Verify correct sorting order
        self.assertEqual([item["portal"] for item in report["top_local"]], 
                         ["high", "medium", "low"])
        
        # Verify counts
        self.assertEqual([item["count"] for item in report["top_local"]], 
                         [3, 2, 1])