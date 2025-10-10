from django.conf import settings
from rest_framework.permissions import BasePermission

def _norm(s: str) -> str:
    return (s or "").strip().upper()

class IsCuratorRole(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        required = _norm(getattr(settings, "CURATOR_ROLE_NAME", "CURATOR"))
        checks = tuple(getattr(settings, "CURATOR_ROLE_CHECKS", ("role", "group")))

        if "role" in checks:
            if _norm(getattr(user, "role", "")) == required:
                return True

        if "group" in checks:
            if user.groups.filter(name=required).exists():
                return True

        return False
