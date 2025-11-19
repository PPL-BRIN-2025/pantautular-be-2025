from rest_framework.permissions import BasePermission, SAFE_METHODS

from authentication.permissions import IsTokenAuthenticated
from .models import ContributorApprovalRole


class IsContributorRole(BasePermission): # pragma: no cover
    """Allow access to contributor submission endpoints."""

    ALLOWED = {"CONTRIBUTOR", "CURATOR", "ADMIN"}

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        role = getattr(user, "role", "")
        return bool(user and role and str(role).upper() in self.ALLOWED)


class ReadOnlyOrContributor(BasePermission): # pragma: no cover
    """Allow unsafe methods only for authenticated contributor roles."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return (
            IsTokenAuthenticated().has_permission(request, view)
            and IsContributorRole().has_permission(request, view)
        )


class IsContributorApproverRole(BasePermission): # pragma: no cover
    """Allow only configured approver roles (plus default fallbacks)."""

    def has_permission(self, request, view):
        return ContributorApprovalRole.user_is_approver(getattr(request, "user", None))
