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


class RoleAssignmentSerializer(serializers.Serializer):
    role_id = serializers.IntegerField(required=False)
    role_name = serializers.CharField(required=False, allow_blank=False)

    default_error_messages = {
        "missing": "Provide either role_id or role_name.",
        "conflict": "Provide only one of role_id or role_name.",
        "not_found": "Invalid role.",
    }

    def validate(self, attrs):
        role_id = attrs.get("role_id")
        role_name = attrs.get("role_name")

        if not role_id and not role_name:
            raise serializers.ValidationError({"detail": self.error_messages["missing"]})
        if role_id and role_name:
            raise serializers.ValidationError({"detail": self.error_messages["conflict"]})

        if role_id:
            role = Role.objects.filter(id=role_id).first()
        else:
            role = Role.objects.filter(name__iexact=role_name).first()

        if role is None:
            raise serializers.ValidationError({"detail": self.error_messages["not_found"]})

        attrs["role"] = role
        return attrs


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "email", "role", "roles"]

    def get_roles(self, obj):
        # Use prefetched roles when available to avoid N+1 queries
        prefetched = getattr(obj, "_prefetched_roles", None)
        if prefetched is not None:
            return [ur.role.name for ur in prefetched if ur.role]

        return list(
            UserRole.objects.filter(user=obj)
            .select_related("role")
            .values_list("role__name", flat=True)
        )

