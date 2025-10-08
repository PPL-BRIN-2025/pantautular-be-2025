# curator_feature/serializers.py
from rest_framework import serializers
from .models import BackendCase

class BackendCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackendCase
        fields = (
            "id", "gender", "age", "city", "status",
            "disease_id", "location_id", "severity",
        )
