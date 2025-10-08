from rest_framework.permissions import BasePermission

class IsCuratorRole(BasePermission):
    """
    Allow only users whose role string equals 'CURATOR'.
    Adjust the check if your project stores roles differently.
    """
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        role = getattr(user, "role", None)
        return bool(user and role and str(role).upper() == "CURATOR")
