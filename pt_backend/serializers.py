from rest_framework import serializers

class CaseLocationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    location__longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    location__latitude = serializers.DecimalField(max_digits=8, decimal_places=6)
    city = serializers.CharField(max_length=255)

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