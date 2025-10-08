from rest_framework import serializers
from django.db import transaction
from pt_backend.models import Case, Disease, Location, News


# ---------- Helpers to resolve related objects by human-friendly names ----------
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

        # Create if all required fields provided
        missing = [k for k in ("province", "latitude", "longitude") if k not in data]
        if missing:
            raise serializers.ValidationError({
                "location": f"Location '{city}' not found. Provide {', '.join(missing)} to create it."
            })

        return Location.objects.create(
            city=city,
            province=str(data["province"]).strip(),
            latitude=data["latitude"],
            longitude=data["longitude"],
        )


class NewsInlineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = News
        fields = ["portal", "title", "type", "content", "url", "author", "date_published", "img_url"]


class NewsInlineReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = News
        fields = ["id", "portal", "title", "type", "content", "url", "author", "date_published", "img_url"]


# ---------- Write serializer (POST/PATCH/PUT) ----------
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
            "status", "severity",  # validated by the choice fields above
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
