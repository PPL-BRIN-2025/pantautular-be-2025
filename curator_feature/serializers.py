from rest_framework import serializers
from django.db import transaction
from .models import CuratorDataLog, DashboardDownloadEvent, DownloadLog
from curator_feature.value_objects import ChartFilters
from pt_backend.models import Case, Disease, Location, News


# CURATOR DATA LOG SERIALIZER 
class CuratorDataLogSerializer(serializers.ModelSerializer):
    lastEdited = serializers.DateTimeField(source="last_edited", read_only=True)
    submittedBy = serializers.CharField(source="submitted_by", read_only=True)
    submitted_by = serializers.CharField(read_only=True)    # snake case alias for tests

    class Meta:
        model = CuratorDataLog
        fields = ("id", "data_id", "title", "lastEdited", "submittedBy", "submitted_by", "note")


# DISEASE SERIALIZER 
class DiseaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disease
        fields = ["id", "name", "level_of_alertness"]
        extra_kwargs = {
            "level_of_alertness": {"required": False, "default": 1},
        }


# SHARED HELPERS 
class CaseInsensitiveChoiceField(serializers.ChoiceField):
    """Choice field that normalizes string inputs to lower-case before validation."""
    def to_internal_value(self, data):
        if isinstance(data, str):
            data = data.lower()
        return super().to_internal_value(data)


# CHART / DOWNLOAD SERIALIZERS 
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


class LocationByNameSerializer(serializers.Serializer):
    """
    Resolve a location by city name (optionally province).
    - If exactly one match is found -> reuse it.
    - If multiple cities match and 'province' not provided -> ask for province.
    - If none found:
        * create only if province + latitude + longitude are provided
        * otherwise return a helpful 400 asking for the missing fields
    """
    city = serializers.CharField()
    province = serializers.CharField(required=False)
    latitude = serializers.DecimalField(max_digits=8, decimal_places=6, required=False)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)

    def resolve(self) -> Location:
        data = self.validated_data
        city = data["city"].strip()

        qs = Location.objects.filter(city__iexact=city)
        prov = data.get("province")
        if prov:
            qs = qs.filter(province__iexact=prov.strip())

        count = qs.count()
        if count == 1:
            return qs.first()

        if count > 1 and not prov:
            raise serializers.ValidationError({
                "location": f"Multiple locations named '{city}'. Provide 'province' to disambiguate."
            })

        # Create if at least province provided; latitude/longitude are optional
        missing = [k for k in ("province",) if k not in data]
        if missing:
            raise serializers.ValidationError({
                "location": f"Location '{city}' not found. Provide province to create it."
            })

        return Location.objects.create(
            city=city,
            province=str(data["province"]).strip(),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
        )


class NewsInlineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = News
        fields = ["portal", "title", "type", "content", "url", "author", "date_published", "img_url"]


class NewsInlineReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = News
        fields = ["id", "portal", "title", "type", "content", "url", "author", "date_published", "img_url"]


class CaseWriteSerializer(serializers.ModelSerializer):
    """
    Accepts:
      - disease by NAME (field 'disease')
      - location by CITY (and optional province; can create with lat/lon+province)
      - inline 'news' for source/summary/etc (creates or updates latest)
    """
    STATUS_CHOICES = ["bahaya", "biasa", "katastropik", "minimal"]
    SEVERITY_CHOICES = ["insiden", "hospitalisasi", "mortalitas"]

    disease = serializers.CharField(write_only=True)
    location = LocationByNameSerializer(write_only=True)
    news = NewsInlineWriteSerializer(write_only=True)
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    severity = serializers.ChoiceField(choices=SEVERITY_CHOICES)

    class Meta:
        model = Case
        fields = [
            "id",
            "gender", "age", "city",
            "status", "severity",
            "disease",
            "location",
            "news",
        ]
    read_only_fields = ["id"]

    def _resolve_disease_id(self, name: str):
        try:
            return Disease.objects.get(name__iexact=name.strip()).id
        except Disease.DoesNotExist:
            raise serializers.ValidationError({"disease": f"Disease '{name}' not found"})

    @transaction.atomic
    def create(self, validated_data):
        disease_name = validated_data.pop("disease")
        loc_data = validated_data.pop("location")
        news_data = validated_data.pop("news")

        loc_ser = LocationByNameSerializer(data=loc_data)
        loc_ser.is_valid(raise_exception=True)
        location = loc_ser.resolve()

        case = Case.objects.create(
            disease_id=self._resolve_disease_id(disease_name),
            location=location,
            **validated_data,
        )
        News.objects.create(case=case, **news_data)
        return case

    @transaction.atomic
    def update(self, instance, validated_data):
        if "disease" in validated_data:
            instance.disease_id = self._resolve_disease_id(validated_data.pop("disease"))

        if "location" in validated_data:
            lser = LocationByNameSerializer(data=validated_data.pop("location"))
            lser.is_valid(raise_exception=True)
            instance.location = lser.resolve()

        news_data = validated_data.pop("news", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()

        if news_data:
            latest = instance.news.order_by("date_published", "id").last()
            if latest:
                for k, v in news_data.items():
                    setattr(latest, k, v)
                latest.save()
            else:
                News.objects.create(case=instance, **news_data)
        return instance


class LocationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "city", "province", "latitude", "longitude"]


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "city", "province", "latitude", "longitude"]
        extra_kwargs = {
            "latitude": {"required": False, "allow_null": True},
            "longitude": {"required": False, "allow_null": True},
        }


class CaseReadSerializer(serializers.ModelSerializer):
    disease_name = serializers.CharField(source="disease.name", read_only=True)
    location = LocationReadSerializer(read_only=True)
    news = NewsInlineReadSerializer(many=True, read_only=True)

    class Meta:
        model = Case
        fields = [
            "id",
            "gender", "age", "city", "status", "severity",
            "disease_name",
            "location",
            "news",
        ]

class LocationByNameSerializer(serializers.Serializer):
    city = serializers.CharField()
    province = serializers.CharField(required=False)
    latitude = serializers.DecimalField(max_digits=8, decimal_places=6, required=False)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)

    def resolve(self) -> Location:
        data = self.validated_data
        city = data["city"].strip()

        qs = Location.objects.filter(city__iexact=city)
        prov = data.get("province")
        if prov:
            qs = qs.filter(province__iexact=prov.strip())

        count = qs.count()
        if count == 1:
            return qs.first()

        if count > 1 and not prov:
            # unchanged: ambiguous without province
            raise serializers.ValidationError({
                "location": f"Multiple locations named '{city}'. Provide 'province' to disambiguate."
            })

        # --- CHANGED: not found -> require province + latitude + longitude ---
        missing_any = any(
            key not in data or data[key] in ("", None)
            for key in ("province", "latitude", "longitude")
        )
        if missing_any:
            raise serializers.ValidationError({
                "location": (
                    f"Location '{city}' not found. Provide province, latitude, longitude to create it."
                )
            })

        # Create with all required fields present
        return Location.objects.create(
            city=city,
            province=str(data["province"]).strip(),
            latitude=data["latitude"],
            longitude=data["longitude"],
        )