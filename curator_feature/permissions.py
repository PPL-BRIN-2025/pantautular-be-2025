from django.conf import settings
from rest_framework.permissions import SAFE_METHODS, BasePermission
from authentication.permissions import IsTokenAuthenticated


class IsCuratorRole(BasePermission):
    """Grant access when the request user matches the configured curator role.

    The verification strategies are controlled via ``CURATOR_ROLE_CHECKS`` in settings.
    Supported strategies:
    - ``"role"``: compare the ``user.role`` attribute (case-insensitive).
    - ``"group"``: require membership in a Django Group named ``CURATOR_ROLE_NAME``.
    Unknown strategies are ignored to keep behaviour backward compatible.
    """

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user:
            return False

        target_role = (getattr(settings, "CURATOR_ROLE_NAME", "CURATOR") or "CURATOR").upper()
        strategies = getattr(settings, "CURATOR_ROLE_CHECKS", ("role",))

        for strategy in strategies:
            if strategy == "role":
                role_value = getattr(user, "role", None)
                if role_value and str(role_value).upper() == target_role:
                    return True
            elif strategy == "group":
                groups = getattr(user, "groups", None)
                try:
                    if groups and groups.filter(name__iexact=target_role).exists():
                        return True
                except Exception:
                    # When groups is a simple list/iterable (e.g. in tests), normalise it.
                    try:
                        if any(str(getattr(g, "name", g)).upper() == target_role for g in groups):
                            return True
                    except Exception:
                        continue
            else:
                continue

        return False

class ReadOnlyOrCurator(BasePermission):
    """Allow safe methods to everyone; otherwise enforce curator auth."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        # For non-safe methods require the same checks as curator base view
        # We rely on the IsTokenAuthenticated permission and IsCuratorRole.
        is_token_auth = IsTokenAuthenticated().has_permission(request, view)
        is_curator = IsCuratorRole().has_permission(request, view)
        return bool(is_token_auth and is_curator)
