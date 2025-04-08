from django.test import TestCase
from pt_backend.serializers import LocationSeverityStatsSerializer

class LocationSeverityStatsSerializerTestCase(TestCase):
    def test_location_severity_stats_serializer(self):
        """Test that LocationSeverityStatsSerializer correctly serializes location stats"""
        data = {
            "name": "Test Location",
            "severity_counts": {
                "hospitalisasi": 10,
                "insiden": 5,
                "mortalitas": 2
            },
            "total_cases": 17
        }
        serializer = LocationSeverityStatsSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Test Location")
        self.assertEqual(serializer.validated_data["severity_counts"]["hospitalisasi"], 10)
        self.assertEqual(serializer.validated_data["severity_counts"]["insiden"], 5)
        self.assertEqual(serializer.validated_data["severity_counts"]["mortalitas"], 2)
        self.assertEqual(serializer.validated_data["total_cases"], 17)