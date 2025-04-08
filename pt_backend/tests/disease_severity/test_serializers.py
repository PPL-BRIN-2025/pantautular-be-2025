from django.test import TestCase
from pt_backend.serializers import DiseaseSeverityStatsSerializer, SeverityCountsSerializer

class DiseaseSeverityStatsSerializerTestCase(TestCase):
    def test_severity_counts_serializer(self):
        """Test that SeverityCountsSerializer correctly serializes data"""
        data = {
            "hospitalisasi": 10,
            "insiden": 5,
            "mortalitas": 2
        }
        serializer = SeverityCountsSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data, data)
    
    def test_disease_severity_stats_serializer(self):
        """Test that DiseaseSeverityStatsSerializer correctly serializes disease stats"""
        data = {
            "name": "Test Disease",
            "severity_counts": {
                "hospitalisasi": 10,
                "insiden": 5,
                "mortalitas": 2
            },
            "total_cases": 17
        }
        serializer = DiseaseSeverityStatsSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Test Disease")
        self.assertEqual(serializer.validated_data["severity_counts"]["hospitalisasi"], 10)
        self.assertEqual(serializer.validated_data["severity_counts"]["insiden"], 5)
        self.assertEqual(serializer.validated_data["severity_counts"]["mortalitas"], 2)
        self.assertEqual(serializer.validated_data["total_cases"], 17)