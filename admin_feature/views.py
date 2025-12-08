# admin_feature/views.py
import logging

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.db.models import Prefetch, Q
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.generics import ListAPIView, DestroyAPIView
from rest_framework.exceptions import ValidationError as DRFValidationError

from authentication.security import CustomJWTAuthentication
from authentication.permissions import IsTokenAuthenticated
from admin_feature.permissions import IsAdminRole
from pantau_tular.security import InputValidator, SafeLogger

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
    def get(self, request):
        summary = self.dashboard_service.get_roles_summary()
        self.log(request=request, action="VIEW", detail="Viewed roles summary")
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class FailedLoginStatsAPIView(AuditLogMixin, AdminDashboardServiceMixin, _AdminBaseAPIView):
    def get(self, request):
        stats = self.dashboard_service.get_failed_login_stats()
        self.log(request=request, action="VIEW", detail="Viewed failed login stats")
        return Response(stats.to_dict(), status=status.HTTP_200_OK)


class FailedLoginEventsAPIView(AuditLogMixin, AdminDashboardServiceMixin, _AdminBaseAPIView):
    def get(self, request):
        events = self.dashboard_service.get_failed_login_events()
        self.log(request=request, action="VIEW", detail="Viewed failed login events")
        return Response(events.to_dict(), status=status.HTTP_200_OK)


class UsersSummaryAPIView(AuditLogMixin, AdminDashboardServiceMixin, _AdminBaseAPIView):
    def get(self, request):
        summary = self.dashboard_service.get_users_summary()
        self.log(request=request, action="VIEW", detail="Viewed users summary")
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class DatasetsSummaryAPIView(AuditLogMixin, AdminDashboardServiceMixin, _AdminBaseAPIView):
    def get(self, request):
        summary = self.dashboard_service.get_datasets_summary()
        self.log(request=request, action="VIEW", detail="Viewed datasets summary")
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class StatsAPIView(AuditLogMixin, AdminDashboardServiceMixin, _AdminBaseAPIView):
    def get(self, request):
        summary = self.dashboard_service.get_stats()
        self.log(request=request, action="VIEW", detail="Viewed dashboard stats")
        return Response(summary.to_dict(), status=status.HTTP_200_OK)


class UserInfoAPIView(_AdminBaseAPIView, AuditLogMixin):
    def get(self, request):
        user = getattr(request, "user", None)
        if not user:
            return Response({"detail": "Authentication credentials were not provided."},
                            status=status.HTTP_401_UNAUTHORIZED)

        role = (getattr(user, "role", "") or "").upper()
        if role != "ADMIN":
            return Response({"detail": "Akses Ditolak"}, status=status.HTTP_403_FORBIDDEN)

        name = getattr(user, "name", None) or getattr(user, "email", "")
        # Use mixin-provided logging helper
        self.log(request=request, action="VIEW", detail="Viewed own admin user info")
        return Response({"name": name, "role": role}, status=status.HTTP_200_OK)


class AdminUserChangeRoleView(APIView, AuditLogMixin):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]

    @transaction.atomic
    def put(self, request, id):
        try:
            user = User.objects.get(id=id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        assignment = RoleAssignmentSerializer(data=request.data)
        assignment.is_valid(raise_exception=True)
        role_obj = assignment.validated_data["role"]

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
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class AdminUserListView(ListAPIView, AuditLogMixin):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    serializer_class = UserSerializer

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
        self.log(request=request, action="VIEW", detail="Viewed admin users list")
        return super().list(request, *args, **kwargs)


class AdminUserDeleteView(DestroyAPIView, AuditLogMixin):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    lookup_field = "id"
    queryset = User.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user_id = getattr(instance, "id", None)
        user_email = getattr(instance, "email", "")
        response = super().destroy(request, *args, **kwargs)
        self.log(
            request=request,
            action="DELETE_USER",
            detail=f"Deleted user id={user_id} email={user_email}",
            note=f"path={request.path} method={request.method}"
        )
        return response


class AdminUserLogsAPIView(APIView, AuditLogMixin, PaginationMixin, SearchMixin, DateFilterMixin):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    validator = InputValidator
    safe_logger = SafeLogger(logging.getLogger(__name__))

    def get(self, request):
        page, page_size = self.get_pagination_params(request)

        raw_search = (request.query_params.get("search") or "").strip()
        raw_sort = request.query_params.get("sort") or "timestamp:desc"
        raw_start = request.query_params.get("start") or ""
        raw_end = request.query_params.get("end") or ""

        try:
            search = self.validator.validate_safe_text(raw_search)
            start = self.validator.validate_safe_text(raw_start)
            end = self.validator.validate_safe_text(raw_end)
            sort = self._validate_sort(raw_sort)
        except DjangoValidationError as exc:
            context = {
                "search": self.validator.sanitize_for_logging(raw_search),
                "sort": self.validator.sanitize_for_logging(raw_sort),
                "start": self.validator.sanitize_for_logging(raw_start),
                "end": self.validator.sanitize_for_logging(raw_end),
            }
            self.safe_logger.warning("Rejected admin log filters %s", context)
            raise DRFValidationError(str(exc))

        order = f"-{sort[0]}" if sort[1] == "desc" else sort[0]

        qs = AdminUserLog.objects.all()
        qs = self.apply_search(qs, search, ["username", "email", "detail"])
        qs = self.apply_date_filter(qs, start, "timestamp__gte")
        qs = self.apply_date_filter(qs, end, "timestamp__lte")

        total = qs.count()
        items = qs.order_by(order)[(page - 1) * page_size : page * page_size]
        data = AdminUserLogSerializer(items, many=True).data

        return Response(
            {"data": data, "page": page, "pageSize": page_size, "total": total},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        data = request.data.copy()
        if "timestamp" not in data:
            data["timestamp"] = timezone.now()

        ser = AdminUserLogSerializer(data=data)
        if ser.is_valid():
            obj = ser.save()
            return Response(AdminUserLogSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response({"errors": ser.errors}, status=status.HTTP_400_BAD_REQUEST)

    def _validate_sort(self, raw_sort: str):
        sanitized = self.validator.validate_safe_text(raw_sort or "timestamp:desc") or "timestamp:desc"
        field, _, direction = sanitized.partition(":")
        field = self.validator.validate_keyword(field or "timestamp")
        direction = (direction or "desc").lower()
        allowed_fields = {"timestamp", "username", "email"}
        if field not in allowed_fields:
            raise DjangoValidationError("Unsupported sort field.")
        if direction not in {"asc", "desc"}:
            raise DjangoValidationError("Sort direction must be either asc or desc.")
        return field, direction



class AdminUserLogDetailAPIView(AuditLogMixin, generics.RetrieveAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    queryset = AdminUserLog.objects.all()
    serializer_class = AdminUserLogDetailSerializer
    lookup_field = "id"

    def retrieve(self, request, *args, **kwargs):
        self.log(request=request, action="VIEW", detail="Viewed user-log detail")
        return super().retrieve(request, *args, **kwargs)


class AdminUserLogUpdateAPIView(AuditLogMixin, generics.RetrieveUpdateAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]
    queryset = AdminUserLog.objects.all()
    serializer_class = AdminUserLogSerializer
    lookup_field = "id"

    def retrieve(self, request, *args, **kwargs):
        self.log(request=request, action="VIEW", detail="Viewed user-log (retrieve)")
        return super().retrieve(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        resp = super().partial_update(request, *args, **kwargs)
        instance = self.get_object()
        self.log(
            request=request,
            action="UPDATE",
            detail=f"Patched AdminUserLog id={instance.id}",
            note=f"path={request.path} method={request.method}",
        )
        return resp


class AdminUserLogsAllAPIView(APIView, AuditLogMixin):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]

    def get(self, request):
        logs = AdminUserLog.objects.all().order_by("-timestamp")
        data = AdminUserLogSerializer(logs, many=True).data
        self.log(request=request, action="VIEW", detail="Viewed all user-logs")
        return Response({"count": len(data), "logs": data}, status=status.HTTP_200_OK)
