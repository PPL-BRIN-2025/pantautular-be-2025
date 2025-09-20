from rest_framework.permissions import BasePermission

class IsAdminRole(BasePermission):
    """
    Allows access only to authenticated users whose current string flag == 'ADMIN'.
    Works with your CustomJWTAuthentication that yields pt_backend.models.User.
    """
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and getattr(user, "role", None) == "ADMIN")
