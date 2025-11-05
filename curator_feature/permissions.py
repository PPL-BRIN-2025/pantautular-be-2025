from rest_framework.permissions import BasePermission
from rest_framework.permissions import SAFE_METHODS
from authentication.permissions import IsTokenAuthenticated

ALLOWED_ROLES = {"CURATOR", "ADMIN", "EXP_USER"}  # adjust if needed

class IsCuratorRole(BasePermission):
    """
    Allow only users whose role is one of the allowed roles.
    """
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        role = getattr(user, "role", None)
        return bool(user and role and str(role).upper() in ALLOWED_ROLES)


class ReadOnlyOrCurator(BasePermission):
    """
    Allow safe methods (GET, HEAD, OPTIONS) to everyone.
    For unsafe methods (POST, PUT, PATCH, DELETE) require token auth AND allowed role.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        is_token_auth = IsTokenAuthenticated().has_permission(request, view)
        is_curator = IsCuratorRole().has_permission(request, view)
        return bool(is_token_auth and is_curator)