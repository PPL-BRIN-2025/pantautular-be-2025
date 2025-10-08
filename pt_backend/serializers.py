from rest_framework import serializers
from .constants import PROVINCE_TO_CODE
from .models import DownloadEvent


class CaseInsensitiveChoiceField(serializers.ChoiceField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            data = data.lower()
        return super().to_internal_value(data)

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

class ProvinceClimateSerializer(serializers.Serializer):
    province = serializers.CharField()
    value = serializers.DecimalField(max_digits=8, decimal_places=2)
    
    def to_representation(self, instance):
        return {
            'id': PROVINCE_TO_CODE.get(instance['province'], instance['province']),
            'value': float(instance['value'])
        }

ProvinceHumiditySerializer = ProvinceClimateSerializer
ProvinceTemperatureSerializer = ProvinceClimateSerializer
ProvincePrecipitationSerializer = ProvinceClimateSerializer


class DownloadLogSerializer(serializers.Serializer):
    metric = CaseInsensitiveChoiceField(choices=DownloadEvent.Metric.choices)
    file_format = CaseInsensitiveChoiceField(choices=DownloadEvent.FileFormat.choices)
    filters = serializers.JSONField(required=False)
    source = serializers.CharField(required=False, allow_blank=True)

    def validate_file_format(self, value):
        return value.lower()
