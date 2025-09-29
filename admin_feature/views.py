# admin_feature/views.py
from django.db import transaction

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListAPIView, DestroyAPIView

from authentication.security import CustomJWTAuthentication
from authentication.permissions import IsTokenAuthenticated
# Reuse the same ADMIN gate as feature 1
from admin_feature.permissions import IsAdminRole  # or: from admin_user.permissions import IsAdminRole

from pt_backend.models import Role, User, UserRole
from .serializers import UserSerializer
from .services import AdminDashboardService


class _AdminBaseAPIView(APIView):
    """
    Base class to unify auth/perm with Feature 1:
    - JWT auth via CustomJWTAuthentication
    - Must be authenticated
    - Must have ADMIN role (string flag on user.role)
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]


class AdminDashboardServiceMixin:
    service_class = AdminDashboardService

    def get_dashboard_service(self) -> AdminDashboardService:
        return self.service_class()

    @property
    def dashboard_service(self) -> AdminDashboardService:
        if not hasattr(self, "_dashboard_service"):
            self._dashboard_service = self.get_dashboard_service()
        return self._dashboard_service


class RolesSummaryAPIView(AdminDashboardServiceMixin, _AdminBaseAPIView):
    """
    GET /admin-feature/roles/summary
    Response:
    {
      "count": int,
      "roles": [str, ...]
    }
    """
    def get(self, request):
        summary = self.dashboard_service.get_roles_summary()
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class FailedLoginStatsAPIView(AdminDashboardServiceMixin, _AdminBaseAPIView):
    """
    GET /admin-feature/failed-logins/stats
    Response:
    {
      "total_failed": int,
      "total_unique_emails": int,
      "last_24h": int,
      "logs_url": "/admin-feature/failed-logins/logs"
    }
    """
    def get(self, request):
        stats = self.dashboard_service.get_failed_login_stats()
        return Response(stats.to_dict(), status=status.HTTP_200_OK)


class FailedLoginEventsAPIView(AdminDashboardServiceMixin, _AdminBaseAPIView):
    """
    GET /admin-feature/failed-logins/logs
    Response:
    {
      "count": int,
      "events": [{ email, timestamp, ip, ...}, ...]  # last 200, reverse chrono
    }
    """
    def get(self, request):
        events = self.dashboard_service.get_failed_login_events()
        return Response(events.to_dict(), status=status.HTTP_200_OK)


class UsersSummaryAPIView(AdminDashboardServiceMixin, _AdminBaseAPIView):
    """
    GET /admin-feature/users/summary
    Response: { "total_users": int, "active_users": int }
    """
    def get(self, request):
        summary = self.dashboard_service.get_users_summary()
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class DatasetsSummaryAPIView(AdminDashboardServiceMixin, _AdminBaseAPIView):
    """
    GET /admin-feature/datasets/summary
    Response: { "total_datasets": int }
    """
    def get(self, request):
        summary = self.dashboard_service.get_datasets_summary()
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class StatsAPIView(AdminDashboardServiceMixin, _AdminBaseAPIView):
    """
    GET /admin-feature/stats
    Response:
    {
      "totalUsers": int,
      "activeUsers": int,
      "datasets": int,
      "failedLogins": int,
      "roles": [str, ...],
      # Optional hints the FE/tests expect when empty or partially empty:
      "empty": bool,
      "isEmpty": bool,
      "message": "Data tidak ditemukan",
      "messages": {
         "usersMessage": "Data tidak ditemukan",
         "activityMessage": "Tidak ada aktivitas",
         "datasetsMessage": "Data tidak ditemukan"
      }
    }
    """
    def get(self, request):
        summary = self.dashboard_service.get_stats()
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class UserInfoAPIView(_AdminBaseAPIView):
    """
    GET /admin-feature/user-info
    Contract:
      - Uses the same JWT + ADMIN gating as Feature 1 (no manual JWT decode, no API key).
      - Returns the logged-in user's display name and role (uppercased).
      - 401 if not authenticated, 403 if authenticated but not ADMIN.
    Response: { "name": str, "role": str }
    """
    def get(self, request):
        user = getattr(request, "user", None)
        # IsTokenAuthenticated already ensures user exists; IsAdminRole ensures role == 'ADMIN'
        # But let's be explicit with messages similar to old behavior:
        if not user:
            return Response({"detail": "Authentication credentials were not provided."},
                            status=status.HTTP_401_UNAUTHORIZED)

        role = (getattr(user, "role", "") or "").upper()
        if role != "ADMIN":
            return Response({"detail": "Akses Ditolak"}, status=status.HTTP_403_FORBIDDEN)

        name = getattr(user, "name", None) or getattr(user, "email", "")
        return Response({"name": name, "role": role}, status=status.HTTP_200_OK)

# Admin role Management (append)

class AdminUserChangeRoleView(APIView):
    """
    PUT /admin/users/<int:id>/role
    Body: { "role_id": 2 }  or  { "role_name": "Curator" }
    Behavior:
      - Update string flag user.role
      - Replace all rows in UserRole for that user with the chosen role (single-role policy)
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]

    @transaction.atomic
    def put(self, request, id):
        try:
            user = User.objects.get(id=id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        role_obj = None
        role_id = request.data.get("role_id")
        role_name = request.data.get("role_name")

        if role_id is not None:
            role_obj = Role.objects.filter(id=role_id).first()
        elif role_name:
            role_obj = Role.objects.filter(name=role_name).first()

        if role_obj is None:
            return Response({"detail": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST)

        # Update string flag (for quick checks in your existing code paths)
        user.role = role_obj.name
        user.save(update_fields=["role"])

        # Replace mapping in UserRole to reflect the chosen role (single-role model)
        UserRole.objects.filter(user=user).delete()
        UserRole.objects.create(user=user, role=role_obj)

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class AdminUserListView(ListAPIView):
    """
    GET /admin/users
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    serializer_class = UserSerializer
    queryset = User.objects.all().order_by("id")


class AdminUserDeleteView(DestroyAPIView):
    """
    DELETE /admin/users/<int:id>
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    lookup_field = "id"
    queryset = User.objects.all()
