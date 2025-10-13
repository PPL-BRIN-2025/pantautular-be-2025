from rest_framework import serializers

from curator_feature.models import DashboardDownloadEvent, DownloadLog
from curator_feature.value_objects import ChartFilters


class CaseInsensitiveChoiceField(serializers.ChoiceField):
    """Choice field that normalizes string inputs to lower-case before validation."""

    def to_internal_value(self, data):
        if isinstance(data, str):
            data = data.lower()
        return super().to_internal_value(data)


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


class ChartLocationSerializer(serializers.Serializer):
    provinces = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True),
        required=False,
        allow_empty=True,
    )
    cities = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True),
        required=False,
        allow_empty=True,
    )


class ChartDataFiltersSerializer(serializers.Serializer):
    diseases = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True),
        required=False,
        allow_empty=True,
    )
    portals = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True),
        required=False,
        allow_empty=True,
    )
    level_of_alertness = serializers.IntegerField(required=False, min_value=1)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    locations = ChartLocationSerializer(required=False)

    def validate_diseases(self, value):
        return self._unique(value)

    def validate_portals(self, value):
        return self._unique(value)

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date cannot be earlier than start date."})
        return attrs

    def _unique(self, values):
        seen = []
        for item in values:
            if item not in seen:
                seen.append(item)
        return seen

    def to_filters(self):
        if not hasattr(self, "_validated_data"):
            raise AssertionError("`to_filters` requires validated data.")
        chart_filters = ChartFilters.from_validated_data(self.validated_data)
        return chart_filters.to_service_filters()


class DashboardDownloadEventSerializer(serializers.Serializer):
    metric = CaseInsensitiveChoiceField(choices=DashboardDownloadEvent.Metric.choices)
    file_format = CaseInsensitiveChoiceField(choices=DashboardDownloadEvent.FileFormat.choices)
    filters = serializers.JSONField(required=False)
    source = serializers.CharField(max_length=255, required=False, allow_blank=False, trim_whitespace=True)

    def validate_filters(self, value):
        if value is None:
            return None
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be an object.")
        return value

    def validate_source(self, value):
        if not value:
            raise serializers.ValidationError("Source may not be blank.")
        return value
