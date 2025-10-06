# admin_feature/views.py
from datetime import datetime
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.generics import ListAPIView, DestroyAPIView

from authentication.security import CustomJWTAuthentication
from authentication.permissions import IsTokenAuthenticated
from admin_feature.permissions import IsAdminRole

from pt_backend.models import Role, User, UserRole
from .serializers import (
    UserSerializer,
    AdminUserLogSerializer,
    AdminUserLogDetailSerializer,
    PtBackendUserSerializer,
)
from .services import AdminDashboardService
from .models import AdminUserLog, PtBackendUser

# AUDIT TRAIL helper
from admin_feature.audittrail import write_log


class _AdminBaseAPIView(APIView):
    """Base class to unify auth/perm with Feature 1"""
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
    def get(self, request):
        summary = self.dashboard_service.get_roles_summary()
        write_log(request=request, user=request.user, action="VIEW", detail="Viewed roles summary")
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class FailedLoginStatsAPIView(AdminDashboardServiceMixin, _AdminBaseAPIView):
    def get(self, request):
        stats = self.dashboard_service.get_failed_login_stats()
        write_log(request=request, user=request.user, action="VIEW", detail="Viewed failed login stats")
        return Response(stats.to_dict(), status=status.HTTP_200_OK)


class FailedLoginEventsAPIView(AdminDashboardServiceMixin, _AdminBaseAPIView):
    def get(self, request):
        events = self.dashboard_service.get_failed_login_events()
        write_log(request=request, user=request.user, action="VIEW", detail="Viewed failed login events")
        return Response(events.to_dict(), status=status.HTTP_200_OK)


class UsersSummaryAPIView(AdminDashboardServiceMixin, _AdminBaseAPIView):
    def get(self, request):
        summary = self.dashboard_service.get_users_summary()
        write_log(request=request, user=request.user, action="VIEW", detail="Viewed users summary")
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class DatasetsSummaryAPIView(AdminDashboardServiceMixin, _AdminBaseAPIView):
    def get(self, request):
        summary = self.dashboard_service.get_datasets_summary()
        write_log(request=request, user=request.user, action="VIEW", detail="Viewed datasets summary")
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class StatsAPIView(AdminDashboardServiceMixin, _AdminBaseAPIView):
    def get(self, request):
        summary = self.dashboard_service.get_stats()
        write_log(request=request, user=request.user, action="VIEW", detail="Viewed dashboard stats")
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class UserInfoAPIView(_AdminBaseAPIView):
    def get(self, request):
        user = getattr(request, "user", None)
        if not user:
            return Response({"detail": "Authentication credentials were not provided."},
                            status=status.HTTP_401_UNAUTHORIZED)

        role = (getattr(user, "role", "") or "").upper()
        if role != "ADMIN":
            return Response({"detail": "Akses Ditolak"}, status=status.HTTP_403_FORBIDDEN)

        name = getattr(user, "name", None) or getattr(user, "email", "")
        write_log(request=request, user=request.user, action="VIEW", detail="Viewed own admin user info")
        return Response({"name": name, "role": role}, status=status.HTTP_200_OK)


class AdminUserChangeRoleView(APIView):
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

        user.role = role_obj.name
        user.save(update_fields=["role"])
        UserRole.objects.filter(user=user).delete()
        UserRole.objects.create(user=user, role=role_obj)

        write_log(
            request=request,
            user=request.user,
            action="UPDATE_ROLE",
            detail=f"Changed role for user_id={user.id} to '{role_obj.name}'",
            note=f"path={request.path} method={request.method}"
        )
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class AdminUserListView(ListAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    serializer_class = UserSerializer
    queryset = User.objects.all().order_by("id")

    def list(self, request, *args, **kwargs):
        write_log(request=request, user=request.user, action="VIEW", detail="Viewed admin users list")
        return super().list(request, *args, **kwargs)


class AdminUserDeleteView(DestroyAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    lookup_field = "id"
    queryset = User.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user_id = getattr(instance, "id", None)
        user_email = getattr(instance, "email", "")
        response = super().destroy(request, *args, **kwargs)
        write_log(
            request=request,
            user=request.user,
            action="DELETE_USER",
            detail=f"Deleted user id={user_id} email={user_email}",
            note=f"path={request.path} method={request.method}"
        )
        return response


class AdminUserLogsAPIView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]

    def get(self, request):
        try:
            page = int(request.query_params.get("page", 1))
        except ValueError:
            page = 1
        try:
            page_size = int(request.query_params.get("pageSize", 10))
        except ValueError:
            page_size = 10
        page = max(1, page)
        page_size = max(1, min(100, page_size))

        search = (request.query_params.get("search") or "").strip()
        sort = request.query_params.get("sort") or "last_login:desc"
        order = "-last_login" if str(sort).endswith(":desc") else "last_login"

        qs = PtBackendUser.objects.all()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search))

        total = qs.count()
        items = qs.order_by(order)[(page - 1) * page_size : page * page_size]

        data = PtBackendUserSerializer(items, many=True).data
        write_log(request=request, user=request.user, action="VIEW", detail="Viewed user-logs list")
        return Response(
            {"data": data, "page": page, "pageSize": page_size, "total": total},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        payload = request.data.copy()
        if not payload.get("timestamp"):
            payload["timestamp"] = datetime.utcnow().isoformat() + "Z"
        ser = AdminUserLogSerializer(data=payload)
        if ser.is_valid():
            obj = ser.save()
            write_log(
                request=request,
                user=request.user,
                action="CREATE",
                detail="Created AdminUserLog via API",
                note=f"log_id={obj.id}"
            )
            return Response(AdminUserLogSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response({"errors": ser.errors}, status=status.HTTP_400_BAD_REQUEST)


class AdminUserLogDetailAPIView(generics.RetrieveAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    queryset = AdminUserLog.objects.all()
    serializer_class = AdminUserLogDetailSerializer
    lookup_field = "id"

    def retrieve(self, request, *args, **kwargs):
        write_log(request=request, user=request.user, action="VIEW", detail="Viewed user-log detail")
        return super().retrieve(request, *args, **kwargs)


class AdminUserLogUpdateAPIView(generics.RetrieveUpdateAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    queryset = AdminUserLog.objects.all()
    serializer_class = AdminUserLogSerializer
    lookup_field = "id"

    def retrieve(self, request, *args, **kwargs):
        write_log(request=request, user=request.user, action="VIEW", detail="Viewed user-log (retrieve)")
        return super().retrieve(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        resp = super().partial_update(request, *args, **kwargs)
        instance = self.get_object()
        write_log(
            request=request,
            user=request.user,
            action="UPDATE",
            detail=f"Patched AdminUserLog id={instance.id}"
        )
        return resp


class AdminUserLogsAllAPIView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]

    def get(self, request):
        logs = AdminUserLog.objects.all().order_by("-timestamp")
        data = AdminUserLogSerializer(logs, many=True).data
        write_log(request=request, user=request.user, action="VIEW", detail="Viewed all user-logs")
        return Response({"count": len(data), "logs": data}, status=status.HTTP_200_OK)