from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from curator_feature.models import DashboardDownloadEvent
from curator_feature.serializers import CaseInsensitiveChoiceField
from pt_backend.models import Case, Disease, Location, News


class CaseWriteSerializer(serializers.Serializer):
    disease = serializers.CharField()
    gender = serializers.CharField()
    age = serializers.IntegerField()
    city = serializers.CharField()
    status = serializers.CharField()
    severity = serializers.CharField()
    location = serializers.DictField()
    news = serializers.DictField()

    def create(self, validated_data):
        location_data = validated_data.pop("location")
        news_data = validated_data.pop("news")

        disease_name = validated_data.pop("disease")
        disease = Disease.objects.get(name=disease_name)

        location, _ = Location.objects.get_or_create(
            city=location_data.get("city"),
            defaults={
                "province": location_data.get("province"),
                "latitude": location_data.get("latitude"),
                "longitude": location_data.get("longitude"),
            },
        )

        case = Case.objects.create(disease=disease, location=location, **validated_data)

        published = news_data.get("date_published")
        if isinstance(published, str):
            parsed = parse_datetime(published)
            if parsed is None:
                parsed = timezone.now()
            elif timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            news_data["date_published"] = parsed

        News.objects.create(case=case, **news_data)
        return case


class CaseReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = "__all__"


class ExpertDashboardDownloadSerializer(serializers.Serializer):
    """Serializer mirroring curator dashboard downloads but allowing CSV format."""

    metric = CaseInsensitiveChoiceField(choices=DashboardDownloadEvent.Metric.choices)
    file_format = CaseInsensitiveChoiceField(
        choices=tuple(DashboardDownloadEvent.FileFormat.choices) + (("csv", "CSV"),)
    )
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
