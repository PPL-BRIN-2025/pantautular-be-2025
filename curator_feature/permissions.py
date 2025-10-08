from django.contrib.auth.models import Group
from rest_framework.permissions import BasePermission

class IsCuratorRole(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        role = (getattr(user, "role", "") or "").upper()
        if role == "CURATOR":
            return True

        return user.groups.filter(name="CURATOR").exists()
