from rest_framework import serializers
from .models import Location


class CaseLocationSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="case.id")
    city = serializers.CharField(source="case.city")
    latitude = serializers.DecimalField(max_digits=8, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        fields = ["id", "city", "latitude", "longitude"]

    @staticmethod
    def serialize(locations):
        return CaseLocationSerializer(locations, many=True).data
