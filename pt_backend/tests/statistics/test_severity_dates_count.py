from datetime import datetime
from django.utils import timezone
from unittest import TestCase

from pt_backend.statistics.reports.severity_dates_count import SeverityDatesCountReport


class SeverityDatesCountReportTestCase(TestCase):
    def setUp(self):
        self.report = SeverityDatesCountReport()

    def test_generate_report_with_data(self):
        # Create test data with different severities and dates
        cases = [
            {
                "id": 1, 
                "severity": "hospitalisasi", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 1))
            },
            {
                "id": 2, 
                "severity": "hospitalisasi", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 1))
            },
            {
                "id": 3, 
                "severity": "mortalitas", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 2))
            },
            {
                "id": 4, 
                "severity": "insiden", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 3))
            }
        ]
        
        result = self.report.generate_report(cases)
        
        # Check that the result contains all severities
        self.assertIn("hospitalisasi", result)
        self.assertIn("mortalitas", result)
        self.assertIn("insiden", result)
        
        # Check the counts for each severity and date
        hosp_data = result["hospitalisasi"]
        self.assertEqual(len(hosp_data), 1)
        self.assertEqual(hosp_data[0]["date"], "2023-01-01")
        self.assertEqual(hosp_data[0]["count"], 2)
        
        mort_data = result["mortalitas"]
        self.assertEqual(len(mort_data), 1)
        self.assertEqual(mort_data[0]["date"], "2023-01-02")
        self.assertEqual(mort_data[0]["count"], 1)
        
        incid_data = result["insiden"]
        self.assertEqual(len(incid_data), 1)
        self.assertEqual(incid_data[0]["date"], "2023-01-03")
        self.assertEqual(incid_data[0]["count"], 1)

    def test_generate_report_with_empty_data(self):
        result = self.report.generate_report([])
        self.assertEqual(result, {})

    def test_generate_report_with_none_data(self):
        result = self.report.generate_report(None)
        self.assertEqual(result, {})

    def test_generate_report_with_missing_date(self):
        cases = [
            {
                "id": 1, 
                "severity": "hospitalisasi", 
                "news__date_published": None
            },
            {
                "id": 2, 
                "severity": "hospitalisasi", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 1))
            }
        ]
        
        result = self.report.generate_report(cases)
        
        # Check that only cases with valid dates are included
        self.assertIn("hospitalisasi", result)
        self.assertEqual(result["hospitalisasi"][0]["count"], 1)

    def test_generate_report_with_multiple_dates_per_severity(self):
        cases = [
            {
                "id": 1, 
                "severity": "hospitalisasi", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 1))
            },
            {
                "id": 2, 
                "severity": "hospitalisasi", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 2))
            },
            {
                "id": 3, 
                "severity": "hospitalisasi", 
                "news__date_published": timezone.make_aware(datetime(2023, 1, 1))
            }
        ]
        
        result = self.report.generate_report(cases)
        
        # Check that the result contains the correct counts for each date
        self.assertIn("hospitalisasi", result)
        hosp_data = result["hospitalisasi"]
        self.assertEqual(len(hosp_data), 2)
        
        # Sort the data by date to ensure consistent testing
        hosp_data.sort(key=lambda x: x["date"])
        
        self.assertEqual(hosp_data[0]["date"], "2023-01-01")
        self.assertEqual(hosp_data[0]["count"], 2)
        self.assertEqual(hosp_data[1]["date"], "2023-01-02")
        self.assertEqual(hosp_data[1]["count"], 1)