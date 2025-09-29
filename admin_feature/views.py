# admin_feature/views.py
from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
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
from .services import DatasetsService


class _AdminBaseAPIView(APIView):
    """
    Base class to unify auth/perm with Feature 1:
    - JWT auth via CustomJWTAuthentication
    - Must be authenticated
    - Must have ADMIN role (string flag on user.role)
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]


class RolesSummaryAPIView(_AdminBaseAPIView):
    """
    GET /admin-feature/roles/summary
    Response:
    {
      "count": int,
      "roles": [str, ...]
    }
    """
    def get(self, request):
        names = list(Role.objects.values_list("name", flat=True).order_by("name"))
        return Response({"count": len(names), "roles": names}, status=status.HTTP_200_OK)


class FailedLoginStatsAPIView(_AdminBaseAPIView):
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
        total_failed = cache.get("auth:failed_login_total", 0)
        events = cache.get("auth:failed_login_events", [])

        unique_count = cache.get("auth:failed_login_unique_emails_count")
        if unique_count is None:
            unique_count = len({(e.get("email") or "").lower() for e in events if e.get("email")})

        now = timezone.now()
        threshold = now - timedelta(hours=24)
        count_24h = 0
        for e in events:
            ts = e.get("timestamp")
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    # assume UTC for naive timestamps
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= threshold:
                    count_24h += 1
            except Exception:
                continue

        return Response(
            {
                "total_failed": total_failed,
                "total_unique_emails": unique_count,
                "last_24h": count_24h,
                "logs_url": "/admin-feature/failed-logins/logs",
            },
            status=status.HTTP_200_OK,
        )


class FailedLoginEventsAPIView(_AdminBaseAPIView):
    """
    GET /admin-feature/failed-logins/logs
    Response:
    {
      "count": int,
      "events": [{ email, timestamp, ip, ...}, ...]  # last 200, reverse chrono
    }
    """
    def get(self, request):
        events = cache.get("auth:failed_login_events", [])
        recent = list(reversed(events[-200:]))
        return Response({"count": len(recent), "events": recent}, status=status.HTTP_200_OK)


class UsersSummaryAPIView(_AdminBaseAPIView):
    """
    GET /admin-feature/users/summary
    Response: { "total_users": int, "active_users": int }
    """
    def get(self, request):
        total_users = User.objects.count()
        active_users = User.objects.filter(last_login__isnull=False).count()
        return Response({"total_users": total_users, "active_users": active_users}, status=status.HTTP_200_OK)


class DatasetsSummaryAPIView(_AdminBaseAPIView):
    """
    GET /admin-feature/datasets/summary
    Response: { "total_datasets": int }
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.datasets_service = DatasetsService()

    def get(self, request):
        total_datasets = self.datasets_service.get_total_datasets()
        return Response({"total_datasets": total_datasets}, status=status.HTTP_200_OK)


class StatsAPIView(_AdminBaseAPIView):
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
        total_users = User.objects.count()
        active_users = User.objects.filter(last_login__isnull=False).count()

        datasets_service = DatasetsService()
        datasets = datasets_service.get_total_datasets()

        roles = list(Role.objects.values_list("name", flat=True).order_by("name"))
        failed_logins = cache.get("auth:failed_login_total", 0)

        payload = {
            "totalUsers": total_users,
            "activeUsers": active_users,
            "datasets": datasets,
            "failedLogins": failed_logins,
            "roles": roles,
        }

        primary_all_zero = (
            total_users == 0 and active_users == 0 and datasets == 0 and failed_logins == 0
        )
        if primary_all_zero:
            payload["empty"] = True
            payload["isEmpty"] = True
            payload["message"] = "Data tidak ditemukan"
            payload["messages"] = {
                "usersMessage": "Data tidak ditemukan",
                "activityMessage": "Tidak ada aktivitas",
                "datasetsMessage": "Data tidak ditemukan",
            }
        else:
            messages = {}
            if total_users == 0:
                messages["usersMessage"] = "Data tidak ditemukan"
            if active_users == 0:
                messages["activityMessage"] = "Tidak ada aktivitas"
            if datasets == 0:
                messages["datasetsMessage"] = "Data tidak ditemukan"
            if messages:
                payload["messages"] = messages

        return Response(payload, status=status.HTTP_200_OK)


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
