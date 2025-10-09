from rest_framework import serializers

from curator_feature.models import DownloadLog


class DownloadLogRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255, trim_whitespace=True)
    chartType = serializers.CharField(max_length=255, trim_whitespace=True)
    timestamp = serializers.DateTimeField()

    def validate_username(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def validate_chartType(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value


class DownloadLogResponseSerializer(serializers.ModelSerializer):
    chartType = serializers.CharField(source="chart_type")

    class Meta:
        model = DownloadLog
        fields = ("id", "username", "chartType", "timestamp", "created_at")
