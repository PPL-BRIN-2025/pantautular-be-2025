from rest_framework.permissions import BasePermission

class IsTokenAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and hasattr(request.user, 'id') and request.user.id is not None)