from rest_framework import serializers
from pt_backend.models import CaseUploadBatch


class BatchSerializer(serializers.ModelSerializer):
    total_cases = serializers.IntegerField(source="cases.count", read_only=True)

    class Meta:
        model = CaseUploadBatch
        fields = ["id", "filename", "uploaded_at", "total_cases"]