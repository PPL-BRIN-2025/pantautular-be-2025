from rest_framework.permissions import BasePermission
from rest_framework.permissions import SAFE_METHODS
from authentication.permissions import IsTokenAuthenticated

class IsCuratorRole(BasePermission):
    """
    Allow only users whose role string equals 'CURATOR'.
    Adjust the check if your project stores roles differently.
    """
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        role = getattr(user, "role", None)
        return bool(user and role and str(role).upper() == "CURATOR")


class ReadOnlyOrCurator(BasePermission):
    """
    Allow safe methods (GET, HEAD, OPTIONS) to everyone.
    For unsafe methods (POST, PUT, PATCH, DELETE) require token auth and CURATOR role.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        # For non-safe methods require the same checks as curator base view
        # We rely on the IsTokenAuthenticated permission and IsCuratorRole.
        is_token_auth = IsTokenAuthenticated().has_permission(request, view)
        is_curator = IsCuratorRole().has_permission(request, view)
        return bool(is_token_auth and is_curator)