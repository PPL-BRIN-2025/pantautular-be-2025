from rest_framework import serializers
from .models import CuratorDataLog

class CuratorDataLogSerializer(serializers.ModelSerializer):
    lastEdited = serializers.DateTimeField(source="last_edited", read_only=True)
    submittedBy = serializers.CharField(source="submitted_by")

    class Meta:
        model = CuratorDataLog
        fields = ("id", "data_id", "title", "lastEdited", "submittedBy", "note")
