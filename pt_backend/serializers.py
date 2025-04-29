from rest_framework import serializers

class CaseLocationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    location__longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    location__latitude = serializers.DecimalField(max_digits=8, decimal_places=6)
    
    city = serializers.CharField(max_length=255)
    location__province = serializers.CharField(max_length=255)

class PrevalenceSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    total_cases = serializers.IntegerField()
    population = serializers.IntegerField()
    prevalence = serializers.FloatField()

class MonthlyCountSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    count = serializers.IntegerField()

class SeverityCountSerializer(serializers.Serializer):
    def to_representation(self, obj):
        result = {}
        for severity_key, month_data in obj.items():
            result[severity_key] = MonthlyCountSerializer(month_data, many=True).data
        return result

class PortalStatisticsSerializer(serializers.Serializer):
    portal = serializers.CharField()
    news_count = serializers.IntegerField()
    disease_count = serializers.IntegerField()

class TopPortalSerializer(serializers.Serializer):
    portal = serializers.CharField()
    count = serializers.IntegerField()
    
class SeverityCountsSerializer(serializers.Serializer):
    hospitalisasi = serializers.IntegerField()
    insiden = serializers.IntegerField()
    mortalitas = serializers.IntegerField()

class DiseaseSeverityStatsSerializer(serializers.Serializer):
    name = serializers.CharField()
    severity_counts = SeverityCountsSerializer()
    total_cases = serializers.IntegerField()

class LocationSeverityStatsSerializer(serializers.Serializer):
    name = serializers.CharField()
    severity_counts = SeverityCountsSerializer()
    total_cases = serializers.IntegerField()

class ProvinceClimateValueSerializer(serializers.Serializer):
    id = serializers.CharField()
    value = serializers.DecimalField(max_digits=8, decimal_places=2)
