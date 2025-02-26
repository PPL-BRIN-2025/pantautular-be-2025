from rest_framework import serializers
from .models import Case

class CaseLocationSerializer(serializers.ModelSerializer):
    latitude = serializers.DecimalField(source="locations.latitude", max_digits=8, decimal_places=6)
    longitude = serializers.DecimalField(source="locations.longitude", max_digits=9, decimal_places=6)

    class Meta:
        model = Case
        fields = ["id", "city", "latitude", "longitude"]