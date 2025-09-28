from rest_framework import serializers
from pt_backend.models import User, Role, UserRole

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