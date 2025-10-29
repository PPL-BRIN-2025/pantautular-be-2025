from rest_framework.permissions import BasePermission, SAFE_METHODS
from authentication.permissions import IsTokenAuthenticated


class IsExpertUserRole(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        role = getattr(user, "role", None)
        return bool(user and role and str(role).upper() == "EXP_USER")


class ReadOnlyOrExpert(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        is_token_auth = IsTokenAuthenticated().has_permission(request, view)
        is_expert = IsExpertUserRole().has_permission(request, view)
        return bool(is_token_auth and is_expert)
