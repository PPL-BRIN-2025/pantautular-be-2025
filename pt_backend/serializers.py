from rest_framework import serializers

class CaseLocationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    location__longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    location__latitude = serializers.DecimalField(max_digits=8, decimal_places=6)
    city = serializers.CharField(max_length=255)

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