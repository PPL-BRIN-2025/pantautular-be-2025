from rest_framework import serializers
from .models import AdminUserLog

class AdminUserLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminUserLog
        fields = ("id", "username", "email", "timestamp", "detail", "note", "action")


class AdminUserLogDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminUserLog
        fields = ["id", "username", "email", "action", "detail", "created_at"]
