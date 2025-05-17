import unittest

from pt_backend.statistics.reports.national_news import NationalNewsStatisticsReport


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
