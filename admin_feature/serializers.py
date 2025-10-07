from rest_framework import serializers
from pt_backend.models import User, Role, UserRole
from .models import AdminUserLog, PtBackendUser

class AdminUserLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminUserLog
        fields = ("id", "username", "email", "timestamp", "detail", "note", "action", "created_at")
        read_only_fields = ("id", "created_at")

class AdminUserLogDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminUserLog
        fields = ["id", "username", "email", "action", "detail", "created_at"]

class PtBackendUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = PtBackendUser
        fields = ["id", "name", "email", "last_login", "role"]

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name"]

class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "email", "role", "roles"]

    def get_roles(self, obj):
        # Return all role names in UserRole mapping (source of truth for FE table)
        return list(
            UserRole.objects.filter(user=obj)
            .select_related("role")
            .values_list("role__name", flat=True)
        )

