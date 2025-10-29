from rest_framework import serializers
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

        disease = Disease.objects.get(name=validated_data["disease"])

        location, _ = Location.objects.get_or_create(
            city=location_data.get("city"),
            defaults={
                "province": location_data.get("province"),
                "latitude": location_data.get("latitude"),
                "longitude": location_data.get("longitude"),
            },
        )

        case = Case.objects.create(disease=disease, location=location, **validated_data)
        News.objects.create(case=case, **news_data)
        return case


class CaseReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = "__all__"
