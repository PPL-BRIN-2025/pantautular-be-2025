from rest_framework.permissions import BasePermission, SAFE_METHODS
from authentication.permissions import IsTokenAuthenticated


class IsExpertUserRole(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        role = getattr(user, "role", None)
        return bool(user and role and str(role).upper() in {"EXP_USER", "ADMIN"})


class ReadOnlyOrExpert(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return (
            IsTokenAuthenticated().has_permission(request, view)
            and IsExpertUserRole().has_permission(request, view)
        )
    