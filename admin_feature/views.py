# admin_feature/views.py
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.db.models import Prefetch, Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.generics import ListAPIView, DestroyAPIView

from authentication.security import CustomJWTAuthentication
from authentication.permissions import IsTokenAuthenticated
from admin_feature.permissions import IsAdminRole

from pt_backend.models import User, UserRole
from .serializers import (
    UserSerializer,
    AdminUserLogSerializer,
    AdminUserLogDetailSerializer,
    PtBackendUserSerializer,
    RoleAssignmentSerializer,
)
from .services import AdminDashboardService
from .models import AdminUserLog, PtBackendUser

# AUDIT TRAIL helper
from admin_feature.audittrail import write_log
from pantau_tular.monitoring import log_event, record_duration
from pantau_tular import monitoring as monitoring_utils


DEFAULT_ADMIN_FEATURE_SLOW_THRESHOLD_MS = 1000


class AdminMonitoringMixin:
    """Shared helpers to emit structured monitoring events and durations."""

    monitoring_default_threshold_ms = DEFAULT_ADMIN_FEATURE_SLOW_THRESHOLD_MS

    def _monitor_context(self, request, **extra):
        user = getattr(request, "user", None)
        context = {
            "user_id": getattr(user, "id", None),
            "endpoint": getattr(self, "monitoring_endpoint", self.__class__.__name__),
        }
        for key, value in extra.items():
            if value is None:
                continue
            context[key] = value
        return context

    def monitor_duration(self, event: str, request, warn_message: str = None, **extra):
        threshold_ms = getattr(
            settings,
            "ADMIN_FEATURE_SLOW_THRESHOLD_MS",
            self.monitoring_default_threshold_ms,
        )
        return record_duration(
            event,
            threshold_ms=threshold_ms,
            warn_message=warn_message,
            **self._monitor_context(request, **extra),
        )

    def monitor_event(self, event: str, request, **extra):
        context = self._monitor_context(request, **extra)
        log_event(event, **context)

        if getattr(settings, "ADMIN_MONITORING_SEND_TO_SENTRY", False):
            sdk = getattr(monitoring_utils, "sentry_sdk", None)
            if sdk:
                status = str(extra.get("status") or "").lower()
                level = "error" if status in {"error", "exception"} else "warning" if status in {
                    "invalid",
                    "forbidden",
                    "unauthenticated",
                    "not_found",
                    "slow",
                    "locked",
                } else "info"

                if level == "info" and not getattr(settings, "ADMIN_MONITORING_SEND_SUCCESS_TO_SENTRY", False):
                    return

                sdk.capture_message(f"{event} | ctx={context}", level=level)

    def sentry_message(self, message: str, level: str = "info"):
        sdk = getattr(monitoring_utils, "sentry_sdk", None)
        if sdk:
            sdk.capture_message(message, level=level)

    @staticmethod
    def _safe_length(data):
        try:
            if isinstance(data, dict) and "results" in data:
                return len(data.get("results") or [])
            return len(data)
        except Exception:
            return None


class _AdminBaseAPIView(AdminMonitoringMixin, APIView):
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


# --- Small, single-purpose mixins to follow SOLID principles ---
class PaginationMixin:
    """Extract pagination logic so views don't handle parsing/validation themselves."""

    def get_pagination_params(self, request):
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        try:
            page_size = max(1, min(100, int(request.query_params.get("pageSize", 10))))
        except (ValueError, TypeError):
            page_size = 10
        return page, page_size


class SearchMixin:
    """Apply simple icontains search across provided fields."""

    def apply_search(self, qs, search: str, fields: list):
        if not search:
            return qs
        q = Q()
        for f in fields:
            kwargs = {f + "__icontains": search}
            q |= Q(**kwargs)
        return qs.filter(q)


class DateFilterMixin:
    """Apply start/end datetime filters using parse_datetime safely."""

    def apply_date_filter(self, qs, param_value, field_op):
        if not param_value:
            return qs
        try:
            dt = parse_datetime(param_value)
            if dt:
                return qs.filter(**{field_op: dt})
        except (ValueError, TypeError):
            pass
        return qs


class AuditLogMixin:
    """Wrap the write_log dependency behind a method so views use a single responsibility for logging.

    If in the future we want to change the audit implementation this isolates the dependency.
    """

    def log(self, request, action: str, detail: str, note: str = ""):
        try:
            write_log(request=request, user=getattr(request, "user", None), action=action, detail=detail, note=note)
        except Exception:
            # Audit logging should not break the main flow; swallow errors intentionally.
            pass


class RolesSummaryAPIView(AuditLogMixin, AdminDashboardServiceMixin, _AdminBaseAPIView):
    monitoring_endpoint = "admin.roles.summary"

    def get(self, request):
        event = self.monitoring_endpoint
        with self.monitor_duration(event, request):
            summary = self.dashboard_service.get_roles_summary()
        self.monitor_event(f"{event}.success", request, status="success", roles_count=summary.count)
        self.log(request=request, action="VIEW", detail="Viewed roles summary")
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class FailedLoginStatsAPIView(AuditLogMixin, AdminDashboardServiceMixin, _AdminBaseAPIView):
    monitoring_endpoint = "admin.failed_logins.stats"

    def get(self, request):
        event = self.monitoring_endpoint
        with self.monitor_duration(event, request):
            stats = self.dashboard_service.get_failed_login_stats()
        self.monitor_event(
            f"{event}.success",
            request,
            status="success",
            total_failed=stats.total_failed,
            unique_emails=stats.total_unique_emails,
            last_24h=stats.last_24h,
        )
        self.log(request=request, action="VIEW", detail="Viewed failed login stats")
        return Response(stats.to_dict(), status=status.HTTP_200_OK)


class FailedLoginEventsAPIView(AuditLogMixin, AdminDashboardServiceMixin, _AdminBaseAPIView):
    monitoring_endpoint = "admin.failed_logins.events"

    def get(self, request):
        event = self.monitoring_endpoint
        with self.monitor_duration(event, request):
            events = self.dashboard_service.get_failed_login_events()
        self.monitor_event(f"{event}.success", request, status="success", count=len(events.events))
        self.log(request=request, action="VIEW", detail="Viewed failed login events")
        return Response(events.to_dict(), status=status.HTTP_200_OK)


class UsersSummaryAPIView(AuditLogMixin, AdminDashboardServiceMixin, _AdminBaseAPIView):
    monitoring_endpoint = "admin.users.summary"

    def get(self, request):
        event = self.monitoring_endpoint
        with self.monitor_duration(event, request):
            summary = self.dashboard_service.get_users_summary()
        self.monitor_event(
            f"{event}.success",
            request,
            status="success",
            total_users=summary.total_users,
            active_users=summary.active_users,
        )
        self.log(request=request, action="VIEW", detail="Viewed users summary")
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class DatasetsSummaryAPIView(AuditLogMixin, AdminDashboardServiceMixin, _AdminBaseAPIView):
    monitoring_endpoint = "admin.datasets.summary"

    def get(self, request):
        event = self.monitoring_endpoint
        with self.monitor_duration(event, request):
            summary = self.dashboard_service.get_datasets_summary()
        self.monitor_event(f"{event}.success", request, status="success", total_datasets=summary.total_datasets)
        self.log(request=request, action="VIEW", detail="Viewed datasets summary")
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class StatsAPIView(AuditLogMixin, AdminDashboardServiceMixin, _AdminBaseAPIView):
    monitoring_endpoint = "admin.dashboard.stats"

    def get(self, request):
        event = self.monitoring_endpoint
        with self.monitor_duration(event, request):
            summary = self.dashboard_service.get_stats()
        self.monitor_event(
            f"{event}.success",
            request,
            status="success",
            total_users=summary.total_users,
            datasets=summary.datasets,
            failed_logins=summary.failed_logins,
        )
        self.log(request=request, action="VIEW", detail="Viewed dashboard stats")
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class UserInfoAPIView(_AdminBaseAPIView, AuditLogMixin):
    monitoring_endpoint = "admin.user.info"

    def get(self, request):
        user = getattr(request, "user", None)
        if not user:
            self.monitor_event(f"{self.monitoring_endpoint}.unauthenticated", request, status="unauthenticated")
            self.sentry_message("admin.user.info.unauthenticated", level="warning")
            return Response({"detail": "Authentication credentials were not provided."},
                            status=status.HTTP_401_UNAUTHORIZED)

        role = (getattr(user, "role", "") or "").upper()
        if role != "ADMIN":
            self.monitor_event(f"{self.monitoring_endpoint}.forbidden", request, status="forbidden", role=role)
            self.sentry_message("admin.user.info.forbidden", level="warning")
            return Response({"detail": "Akses Ditolak"}, status=status.HTTP_403_FORBIDDEN)

        with self.monitor_duration(self.monitoring_endpoint, request):
            name = getattr(user, "name", None) or getattr(user, "email", "")
        # Use mixin-provided logging helper
        self.log(request=request, action="VIEW", detail="Viewed own admin user info")
        self.monitor_event(f"{self.monitoring_endpoint}.success", request, status="success")
        return Response({"name": name, "role": role}, status=status.HTTP_200_OK)


class AdminUserChangeRoleView(AuditLogMixin, AdminMonitoringMixin, APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    monitoring_endpoint = "admin.users.change_role"

    @transaction.atomic
    def put(self, request, id):
        event = self.monitoring_endpoint
        try:
            user = User.objects.get(id=id)
        except User.DoesNotExist:
            self.monitor_event(f"{event}.not_found", request, status="not_found", target_user_id=id)
            self.sentry_message("admin.users.change_role.not_found", level="warning")
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        with self.monitor_duration(event, request, target_user_id=user.id):
            assignment = RoleAssignmentSerializer(data=request.data)
            assignment.is_valid(raise_exception=True)
            role_obj = assignment.validated_data["role"]
            previous_role = user.role

            if user.role != role_obj.name:
                user.role = role_obj.name
                user.save(update_fields=["role"])

            UserRole.objects.filter(user=user).exclude(role=role_obj).delete()
            UserRole.objects.get_or_create(user=user, role=role_obj)

        self.log(
            request=request,
            action="UPDATE_ROLE",
            detail=f"Changed role for user_id={user.id} to '{role_obj.name}'",
            note=f"path={request.path} method={request.method}"
        )
        self.monitor_event(
            f"{event}.success",
            request,
            status="success",
            target_user_id=user.id,
            new_role=role_obj.name,
            previous_role=previous_role,
        )
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class AdminUserListView(AuditLogMixin, AdminMonitoringMixin, ListAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    serializer_class = UserSerializer
    monitoring_endpoint = "admin.users.list"

    def get_queryset(self):
        return (
            User.objects.all()
            .prefetch_related(
                Prefetch(
                    "roles",
                    queryset=UserRole.objects.select_related("role"),
                    to_attr="_prefetched_roles",
                )
            )
            .order_by("id")
        )

    def list(self, request, *args, **kwargs):
        event = self.monitoring_endpoint
        with self.monitor_duration(event, request):
            response = super().list(request, *args, **kwargs)
        result_count = self._safe_length(getattr(response, "data", None))
        self.monitor_event(f"{event}.success", request, status="success", result_count=result_count)
        self.log(request=request, action="VIEW", detail="Viewed admin users list")
        return response


class AdminUserDeleteView(AuditLogMixin, AdminMonitoringMixin, DestroyAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    lookup_field = "id"
    queryset = User.objects.all()
    monitoring_endpoint = "admin.users.delete"

    def destroy(self, request, *args, **kwargs):
        event = self.monitoring_endpoint
        instance = self.get_object()
        user_id = getattr(instance, "id", None)
        user_email = getattr(instance, "email", "")
        with self.monitor_duration(event, request, target_user_id=user_id):
            response = super().destroy(request, *args, **kwargs)
        self.log(
            request=request,
            action="DELETE_USER",
            detail=f"Deleted user id={user_id} email={user_email}",
            note=f"path={request.path} method={request.method}"
        )
        self.monitor_event(
            f"{event}.success",
            request,
            status="success",
            target_user_id=user_id,
            email=user_email,
        )
        return response


class AdminUserLogsAPIView(APIView, AuditLogMixin, AdminMonitoringMixin, PaginationMixin, SearchMixin, DateFilterMixin):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    monitoring_endpoint = "admin.user_logs"

    def get(self, request):
        event = f"{self.monitoring_endpoint}.list"
        page, page_size = self.get_pagination_params(request)

        search = (request.query_params.get("search") or "").strip()
        sort = request.query_params.get("sort") or "timestamp:desc"
        order = "-timestamp" if str(sort).endswith(":desc") else "timestamp"

        with self.monitor_duration(
            event,
            request,
            page=page,
            page_size=page_size,
            search_applied=bool(search),
            sort=sort,
        ):
            qs = AdminUserLog.objects.all()
            qs = self.apply_search(qs, search, ["username", "email", "detail"])
            qs = self.apply_date_filter(qs, request.query_params.get("start"), "timestamp__gte")
            qs = self.apply_date_filter(qs, request.query_params.get("end"), "timestamp__lte")

            total = qs.count()
            items = qs.order_by(order)[(page - 1) * page_size : page * page_size]
            data = AdminUserLogSerializer(items, many=True).data

        self.monitor_event(
            f"{event}.success",
            request,
            status="success",
            total=total,
            returned=len(data),
        )
        return Response(
            {"data": data, "page": page, "pageSize": page_size, "total": total},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        event = f"{self.monitoring_endpoint}.create"
        data = request.data.copy()
        if "timestamp" not in data:
            data["timestamp"] = timezone.now()

        ser = AdminUserLogSerializer(data=data)
        if ser.is_valid():
            with self.monitor_duration(event, request, username=data.get("username"), action=data.get("action")):
                obj = ser.save()
            self.monitor_event(f"{event}.success", request, status="success", log_id=obj.id)
            return Response(AdminUserLogSerializer(obj).data, status=status.HTTP_201_CREATED)
        self.monitor_event(
            f"{event}.invalid",
            request,
            status="invalid",
            errors=list(ser.errors.keys()),
        )
        self.sentry_message("admin.user_logs.create.invalid", level="warning")
        return Response({"errors": ser.errors}, status=status.HTTP_400_BAD_REQUEST)



class AdminUserLogDetailAPIView(AuditLogMixin, AdminMonitoringMixin, generics.RetrieveAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    queryset = AdminUserLog.objects.all()
    serializer_class = AdminUserLogDetailSerializer
    lookup_field = "id"
    monitoring_endpoint = "admin.user_log.detail"

    def retrieve(self, request, *args, **kwargs):
        event = self.monitoring_endpoint
        log_id = kwargs.get(self.lookup_field)
        with self.monitor_duration(event, request, log_id=log_id):
            response = super().retrieve(request, *args, **kwargs)
        self.log(request=request, action="VIEW", detail="Viewed user-log detail")
        self.monitor_event(f"{event}.success", request, status="success", log_id=log_id)
        return response


class AdminUserLogUpdateAPIView(AuditLogMixin, AdminMonitoringMixin, generics.RetrieveUpdateAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    queryset = AdminUserLog.objects.all()
    serializer_class = AdminUserLogSerializer
    lookup_field = "id"
    monitoring_endpoint = "admin.user_log.update"

    def retrieve(self, request, *args, **kwargs):
        event = f"{self.monitoring_endpoint}.retrieve"
        log_id = kwargs.get(self.lookup_field)
        with self.monitor_duration(event, request, log_id=log_id):
            response = super().retrieve(request, *args, **kwargs)
        self.log(request=request, action="VIEW", detail="Viewed user-log (retrieve)")
        self.monitor_event(f"{event}.success", request, status="success", log_id=log_id)
        return response

    def partial_update(self, request, *args, **kwargs):
        event = self.monitoring_endpoint
        log_id = kwargs.get(self.lookup_field)
        with self.monitor_duration(event, request, log_id=log_id):
            resp = super().partial_update(request, *args, **kwargs)
        instance = self.get_object()
        self.log(
            request=request,
            action="UPDATE",
            detail=f"Patched AdminUserLog id={instance.id}",
            note=f"path={request.path} method={request.method}",
        )
        self.monitor_event(f"{event}.success", request, status="success", log_id=instance.id)
        return resp


class AdminUserLogsAllAPIView(APIView, AuditLogMixin, AdminMonitoringMixin):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    monitoring_endpoint = "admin.user_logs.all"

    def get(self, request):
        event = self.monitoring_endpoint
        with self.monitor_duration(event, request):
            logs = AdminUserLog.objects.all().order_by("-timestamp")
            data = AdminUserLogSerializer(logs, many=True).data
        self.log(request=request, action="VIEW", detail="Viewed all user-logs")
        self.monitor_event(f"{event}.success", request, status="success", total=len(data))
        return Response({"count": len(data), "logs": data}, status=status.HTTP_200_OK)
