from rest_framework import serializers
from .models import AdminUserLog

class AdminUserLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminUserLog
        fields = ("id", "username", "email", "timestamp", "detail", "note", "action", "created_at")
        read_only_fields = ("id", "username", "email", "timestamp", "action", "created_at")

class AdminUserLogDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminUserLog
        fields = ["id", "username", "email", "action", "detail", "created_at"]
