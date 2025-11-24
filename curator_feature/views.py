import logging
from typing import Any, Dict

from django.conf import settings
from django.db.models import Q
from django.http import Http404

from rest_framework.exceptions import ValidationError, PermissionDenied, APIException
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from curator_feature.audittrail import log_curator_action

from authentication.permissions import IsTokenAuthenticated
from authentication.security import CustomJWTAuthentication
from pt_backend.authentication import APIKeyAuthentication

from curator_feature.serializers import (
    # charts/download
    ChartDataFiltersSerializer,
    DashboardDownloadEventSerializer,
    DownloadLogRequestSerializer,
    DownloadLogResponseSerializer,
    # curator cases
    CaseWriteSerializer,
    CaseReadSerializer,
    # audit logs
    CuratorDataLogSerializer,
    ContributorSubmission,
    ContributorSubmissionListSerializer,
    ContributorSubmissionDetailSerializer,
)
from pt_backend.serializers import DiseaseSerializer
from curator_feature.services import (
    ChartDataService,
    DashboardDownloadEventService,
    DownloadLogService,
    ContributorSubmissionService
)
from curator_feature.value_objects import ClientMetadata
from pantau_tular.monitoring import log_event, record_duration
from pt_backend.models import Case

from .models import CuratorDataLog, BackendCase, ContributorSubmission
from .permissions import IsCuratorRole

logger = logging.getLogger(__name__)


def _monitoring_context(request, endpoint: str, **extra: Any) -> Dict[str, Any]:
    """Build structured context for monitoring payloads."""
    user = getattr(getattr(request, "user", None), "id", None)
    meta = getattr(request, "META", None)
    client_ip = meta.get("REMOTE_ADDR") if isinstance(meta, dict) else None
    context: Dict[str, Any] = {
        "endpoint": endpoint,
        "user_id": user,
        "client_ip": client_ip,
    }
    context.update(extra)
    return context


# ===============================
# Charts & Downloads APIs
# ===============================
class ChartsSimpleView(APIView):
    service_class = ChartDataService

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = self.service_class()

    def get(self, request, *args, **kwargs):
        context = _monitoring_context(request, "curator_chart_simple")
        try:
            with record_duration(
                "curator.chart.simple_fetch",
                threshold_ms=getattr(settings, "CURATOR_CHART_FETCH_SLOW_THRESHOLD_MS", 1000),
                **context,
            ):
                payload = self.service.get_chart_data()
        except Exception:
            log_event("curator.chart.simple.failed", status="error", **context)
            logger.exception("Unable to retrieve chart data from pt_backend")
            return Response({"message": "Failed to fetch chart data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        chart_count = len(payload.get("charts") or [])
        log_event("curator.chart.simple.success", status="success", charts=chart_count, **context)
        return Response(payload, status=status.HTTP_200_OK)


class ChartDataAPIView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated]

    request_serializer_class = ChartDataFiltersSerializer
    service_class = ChartDataService

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = self.service_class()

    def get(self, request, *args, **kwargs):
        context = _monitoring_context(request, "curator_chart_get", filters_applied=False)
        try:
            with record_duration(
                "curator.chart.fetch",
                threshold_ms=getattr(settings, "CURATOR_CHART_FETCH_SLOW_THRESHOLD_MS", 1000),
                **context,
            ):
                payload = self.service.get_chart_data(filters=None)
        except Exception:
            log_event("curator.chart.fetch.failed", status="error", **context)
            logger.exception("Unable to retrieve chart data")
            return Response(
                {"message": "Failed to fetch chart data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        log_event("curator.chart.fetch.success", status="success", **context)
        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        base_context = _monitoring_context(request, "curator_chart_post")
        serializer = self.request_serializer_class(data=request.data)
        if not serializer.is_valid():
            logger.debug("Invalid chart data filters: %s", serializer.errors)
            log_event(
                "curator.chart.filters.invalid",
                status="invalid",
                errors=serializer.errors,
                **base_context,
            )
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        filters = serializer.to_filters()
        filters_context = {**base_context, "filters_applied": bool(filters)}
        try:
            with record_duration(
                "curator.chart.fetch",
                threshold_ms=getattr(settings, "CURATOR_CHART_FETCH_SLOW_THRESHOLD_MS", 1000),
                **filters_context,
            ):
                payload = self.service.get_chart_data(filters=filters or None)
        except Exception:
            log_event("curator.chart.fetch.failed", status="error", **filters_context)
            logger.exception("Unable to retrieve chart data with filters")
            return Response(
                {"message": "Failed to fetch chart data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        log_event("curator.chart.fetch.success", status="success", **filters_context)
        return Response(payload, status=status.HTTP_200_OK)


class DownloadLogAPIView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated]

    request_serializer_class = DownloadLogRequestSerializer
    response_serializer_class = DownloadLogResponseSerializer
    service_class = DownloadLogService

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = self.service_class()

    def post(self, request, *args, **kwargs):
        context = _monitoring_context(request, "curator_download_log")
        serializer = self.request_serializer_class(data=request.data)
        if not serializer.is_valid():
            logger.debug("Invalid download log payload: %s", serializer.errors)
            log_event(
                "curator.download_log.invalid_payload",
                status="invalid",
                errors=serializer.errors,
                **context,
            )
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data

        if not getattr(settings, "ENABLE_DOWNLOAD_LOGGING", False):
            log_event("curator.download_log.disabled", status="disabled", **context)
            return Response(
                {"logged": False, "detail": "Download logging disabled"},
                status=status.HTTP_202_ACCEPTED,
            )

        log_context = {
            **context,
            "username": payload.get("username"),
            "chart_type": payload.get("chartType"),
        }
        try:
            with record_duration(
                "curator.download_log.persist",
                threshold_ms=getattr(settings, "CURATOR_DOWNLOAD_LOG_SLOW_THRESHOLD_MS", 500),
                **log_context,
            ):
                log_entry = self.service.log_download(
                    username=payload["username"],
                    chart_type=payload["chartType"],
                    timestamp=payload["timestamp"],
                )
        except Exception:
            log_event("curator.download_log.failed", status="error", **log_context)
            logger.exception(
                "Download logging failed for user=%s chart=%s",
                payload.get("username"),
                payload.get("chartType"),
            )
            return Response(
                {"message": "Download logging failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response_data = self.response_serializer_class(log_entry).data
        log_event(
            "curator.download_log.logged",
            status="success",
            download_log_id=str(log_entry.id),
            **log_context,
        )
        return Response(response_data, status=status.HTTP_201_CREATED)


class DashboardDownloadEventAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    serializer_class = DashboardDownloadEventSerializer
    service_class = DashboardDownloadEventService

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = self.service_class()

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        context = _monitoring_context(
            request,
            "curator_dashboard_download",
            metric=payload.get("metric"),
            file_format=payload.get("file_format"),
        )
        if not getattr(settings, "ENABLE_DOWNLOAD_LOGGING", False):
            log_event("curator.dashboard_download.disabled", status="disabled", **context)
            return Response(
                {"logged": False, "detail": "Download logging disabled"},
                status=status.HTTP_202_ACCEPTED,
            )

        client_metadata = ClientMetadata.from_request(request)
        context = {**context, "client_ip": client_metadata.ip_address}
        try:
            with record_duration(
                "curator.dashboard_download.persist",
                threshold_ms=getattr(settings, "CURATOR_DOWNLOAD_LOG_SLOW_THRESHOLD_MS", 500),
                **context,
            ):
                event = self.service.log_event(
                    metric=payload["metric"],
                    file_format=payload["file_format"],
                    filters=payload.get("filters"),
                    source=payload.get("source"),
                    client=client_metadata,
                )
        except Exception:
            log_event("curator.dashboard_download.failed", status="error", **context)
            raise

        log_event("curator.dashboard_download.logged", status="success", event_id=str(event.id), **context)
        return Response({"id": event.id, "logged": True}, status=status.HTTP_201_CREATED)


# --- Public endpoint for diseases (GET + POST) ---
class DiseaseListCreateView(generics.ListCreateAPIView):
    """Expose GET for everyone and allow POST only for curator users.

    This view accepts POST when the request is authenticated and the user has
    curator role (enforced by ReadOnlyOrCurator permission). Otherwise POST
    will be denied while GET remains public.
    """
    serializer_class = DiseaseSerializer
    # Accept JWT or session-based auth so both token and logged-in users can POST
    authentication_classes = [CustomJWTAuthentication, SessionAuthentication, BasicAuthentication]

    def get_permissions(self):
        # For safe methods allow everyone; for unsafe methods enforce curator checks
        from .permissions import ReadOnlyOrCurator

        if self.request.method in SAFE_METHODS:
            return []
        return [ReadOnlyOrCurator()]

    def get_queryset(self):
        # Lazy import to avoid circular import issues at module import time
        from pt_backend.models import Disease as _Disease

        return _Disease.objects.all().order_by("name")


# ===============================
# Curator Case APIs
# ===============================
class _CuratorBaseView(generics.GenericAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsCuratorRole]


class CuratorCaseListCreateView(_CuratorBaseView, generics.ListCreateAPIView):
    queryset = (
        Case.objects.select_related("disease", "location")
        .prefetch_related("news")
        .order_by("-id")
    )

    def get_serializer_class(self):
        return CaseReadSerializer if self.request.method == "GET" else CaseWriteSerializer

    def list(self, request, *args, **kwargs):
        context = _monitoring_context(request, "curator_case_list")
        try:
            with record_duration(
                "curator.case.list",
                threshold_ms=getattr(settings, "CURATOR_CASE_READ_SLOW_THRESHOLD_MS", 800),
                **context,
            ):
                response = super().list(request, *args, **kwargs)
        except Exception:
            log_event("curator.case.list.failed", status="error", **context)
            raise
        log_event(
            "curator.case.list.success",
            status="success",
            paginated=isinstance(response.data, dict) and "results" in response.data,
            **context,
        )
        return response

    def create(self, request, *args, **kwargs):
        context = _monitoring_context(request, "curator_case_create")
        try:
            with record_duration(
                "curator.case.create",
                threshold_ms=getattr(settings, "CURATOR_CASE_WRITE_SLOW_THRESHOLD_MS", 1200),
                **context,
            ):
                response = super().create(request, *args, **kwargs)
        except ValidationError as exc:
            log_event("curator.case.create.invalid", status="invalid", errors=exc.detail, **context)
            raise
        except Exception:
            log_event("curator.case.create.failed", status="error", **context)
            raise
        case_id = response.data.get("id") if isinstance(response.data, dict) else None
        log_event("curator.case.create.success", status="success", case_id=case_id, **context)
        return response

    # === NEW: catat ke audit log saat CREATE ===
    def perform_create(self, serializer):
        instance = serializer.save()
        try:
            log_curator_action(
                user=self.request.user,
                data_id=instance.id,
                title=(instance.severity or instance.status or "Created"),
                note="Data created by curator.",
            )
        except Exception:
            # jangan ganggu flow utama kalau logging gagal
            logger.exception("audit-log create failed for case %s", instance.id)



class CuratorCaseDetailView(_CuratorBaseView, generics.RetrieveUpdateDestroyAPIView):
    lookup_field = "id"
    queryset = (
        Case.objects.select_related("disease", "location")
        .prefetch_related("news")
        .order_by("-id")
    )

    def get_serializer_class(self):
        # GET returns read serializer; PATCH/PUT use write serializer
        return CaseReadSerializer if self.request.method == "GET" else CaseWriteSerializer

    def retrieve(self, request, *args, **kwargs):
        context = _monitoring_context(
            request,
            "curator_case_detail",
            case_id=str(kwargs.get(self.lookup_field)),
        )
        try:
            with record_duration(
                "curator.case.retrieve",
                threshold_ms=getattr(settings, "CURATOR_CASE_READ_SLOW_THRESHOLD_MS", 800),
                **context,
            ):
                response = super().retrieve(request, *args, **kwargs)
        except Http404:
            log_event("curator.case.retrieve.not_found", status="not_found", **context)
            raise
        except Exception:
            log_event("curator.case.retrieve.failed", status="error", **context)
            raise
        log_event("curator.case.retrieve.success", status="success", **context)
        return response

    def update(self, request, *args, **kwargs):
        context = _monitoring_context(
            request,
            "curator_case_update",
            case_id=str(kwargs.get(self.lookup_field)),
        )
        try:
            with record_duration(
                "curator.case.update",
                threshold_ms=getattr(settings, "CURATOR_CASE_WRITE_SLOW_THRESHOLD_MS", 1200),
                **context,
            ):
                response = super().update(request, *args, **kwargs)
        except ValidationError as exc:
            log_event("curator.case.update.invalid", status="invalid", errors=exc.detail, **context)
            raise
        except Http404:
            log_event("curator.case.update.not_found", status="not_found", **context)
            raise
        except Exception:
            log_event("curator.case.update.failed", status="error", **context)
            raise
        log_event("curator.case.update.success", status="success", **context)
        return response

    def destroy(self, request, *args, **kwargs):
        context = _monitoring_context(
            request,
            "curator_case_delete",
            case_id=str(kwargs.get(self.lookup_field)),
        )
        try:
            with record_duration(
                "curator.case.delete",
                threshold_ms=getattr(settings, "CURATOR_CASE_WRITE_SLOW_THRESHOLD_MS", 1200),
                **context,
            ):
                response = super().destroy(request, *args, **kwargs)
        except Http404:
            log_event("curator.case.delete.not_found", status="not_found", **context)
            raise
        except Exception:
            log_event("curator.case.delete.failed", status="error", **context)
            raise
        log_event("curator.case.delete.success", status="success", **context)
        return response

    # === NEW: catat ke audit log saat UPDATE ===
    def perform_update(self, serializer):
        instance = serializer.save()
        try:
            log_curator_action(
                user=self.request.user,
                data_id=instance.id,
                title=(instance.severity or instance.status or "Updated"),
                note="Data updated by curator.",
            )
        except Exception:
            logger.exception("audit-log update failed for case %s", instance.id)

    # === NEW: catat ke audit log saat DELETE ===
    def perform_destroy(self, instance):
        try:
            log_curator_action(
                user=self.request.user,
                data_id=instance.id,
                title=(getattr(instance, "severity", None) or getattr(instance, "status", None) or "Deleted"),
                note="Data deleted by curator.",
            )
        except Exception:
            logger.exception("audit-log delete failed for case %s", instance.id)
        # lanjut hapus data
        super().perform_destroy(instance)



class CuratorDiseaseListCreateView(_CuratorBaseView, generics.ListCreateAPIView):
    """Curator-only endpoint to list and create Disease records.

    Uses the `DiseaseSerializer` defined in `curator_feature.serializers` and
    enforces curator-level permissions via `_CuratorBaseView`.
    """
    serializer_class = DiseaseSerializer

    def get_queryset(self):
        # Lazy import to avoid circular import issues during module load
        from pt_backend.models import Disease as _Disease

        return _Disease.objects.all().order_by("name")

    def list(self, request, *args, **kwargs):
        context = _monitoring_context(request, "curator_disease_list")
        try:
            with record_duration(
                "curator.disease.list",
                threshold_ms=getattr(settings, "CURATOR_CASE_READ_SLOW_THRESHOLD_MS", 800),
                **context,
            ):
                response = super().list(request, *args, **kwargs)
        except Exception:
            log_event("curator.disease.list.failed", status="error", **context)
            raise
        log_event(
            "curator.disease.list.success",
            status="success",
            result_count=len(response.data) if isinstance(response.data, list) else None,
            **context,
        )
        return response

    def create(self, request, *args, **kwargs):
        context = _monitoring_context(request, "curator_disease_create")
        try:
            with record_duration(
                "curator.disease.create",
                threshold_ms=getattr(settings, "CURATOR_CASE_WRITE_SLOW_THRESHOLD_MS", 1200),
                **context,
            ):
                response = super().create(request, *args, **kwargs)
        except ValidationError as exc:
            log_event("curator.disease.create.invalid", status="invalid", errors=exc.detail, **context)
            raise
        except Exception:
            log_event("curator.disease.create.failed", status="error", **context)
            raise
        disease_id = response.data.get("id") if isinstance(response.data, dict) else None
        log_event("curator.disease.create.success", status="success", disease_id=disease_id, **context)
        return response


# ===============================
# Curator Audit Logs API
# ===============================
class CuratorDataLogListCreateAPIView(APIView):
    authentication_classes = [CustomJWTAuthentication, SessionAuthentication]
    permission_classes = [IsTokenAuthenticated, IsCuratorRole] 

    def get(self, request):
        context = _monitoring_context(request, "curator_audit_log_list")
        # pagination
        def _i(v, d=None):
            try:
                return int(v)
            except Exception:
                return d

        page = max(1, _i(request.query_params.get("page", 1), 1))
        page_size = max(1, min(100, _i(request.query_params.get("pageSize", 10), 10)))

        # filters
        search = (request.query_params.get("search") or "").strip()
        submitted_by = (request.query_params.get("submitted_by") or "").strip()
        start = request.query_params.get("start") or ""
        end = request.query_params.get("end") or ""

        # sorting
        sort = (request.query_params.get("sort") or "last_edited:desc").lower()
        f = sort.split(":")[0]
        d = sort.split(":")[1] if ":" in sort else "desc"
        allowed = {"last_edited", "title", "submitted_by", "data_id"}
        sort_field = f if f in allowed else "last_edited"
        order_by = f"-{sort_field}" if d == "desc" else sort_field

        qs = CuratorDataLog.objects.all()

        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(submitted_by__icontains=search)
                | Q(data_id__icontains=search)
            )
        if submitted_by:
            qs = qs.filter(submitted_by__icontains=submitted_by)
        if start:
            qs = qs.filter(last_edited__gte=start)
        if end:
            qs = qs.filter(last_edited__lte=end)

        try:
            with record_duration(
                "curator.audit_log.list",
                threshold_ms=getattr(settings, "CURATOR_AUDIT_LOG_READ_SLOW_THRESHOLD_MS", 800),
                **context,
            ):
                total = qs.count()
                items = qs.order_by(order_by)[(page - 1) * page_size : page * page_size]
                data = CuratorDataLogSerializer(items, many=True).data
        except Exception:
            log_event("curator.audit_log.list.failed", status="error", **context)
            raise

        log_event("curator.audit_log.list.success", status="success", total=total, **context)
        return Response(
            {"data": data, "page": page, "pageSize": page_size, "total": total},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        # optional helper endpoint to create a log
        payload = request.data.copy()
        context = _monitoring_context(
            request,
            "curator_audit_log_create",
            data_id=payload.get("data_id"),
        )
        # if title not provided, try to derive from pt_backend_case.severity
        if not payload.get("title") and payload.get("data_id"):
            try:
                case = BackendCase.objects.get(id=payload["data_id"])
                payload["title"] = case.severity or "N/A"
            except BackendCase.DoesNotExist:
                pass

        payload["submittedBy"] = getattr(request.user, "username", "") or getattr(
            request.user, "email", ""
        )
        ser = CuratorDataLogSerializer(data=payload)
        if ser.is_valid():
            try:
                with record_duration(
                    "curator.audit_log.create",
                    threshold_ms=getattr(settings, "CURATOR_AUDIT_LOG_WRITE_SLOW_THRESHOLD_MS", 800),
                    **context,
                ):
                    ser.save()
            except Exception:
                log_event("curator.audit_log.create.failed", status="error", **context)
                raise
            log_event(
                "curator.audit_log.create.success",
                status="success",
                log_id=ser.data.get("id"),
                **context,
            )
            return Response(ser.data, status=status.HTTP_201_CREATED)
        log_event("curator.audit_log.create.invalid", status="invalid", errors=ser.errors, **context)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)



logger = logging.getLogger(__name__)


# ============================================================
# LIST VIEW
# ============================================================

class ContributorSubmissionListView(_CuratorBaseView, generics.ListAPIView):
    serializer_class = ContributorSubmissionListSerializer
    service = ContributorSubmissionService()

    def get_queryset(self):
        search = self.request.query_params.get("search")
        status_param = self.request.query_params.get("status")

        try:
            return self.service.list(search=search, status=status_param)
        except Exception:
            logger.exception("Unable to retrieve contributor submissions")
            raise APIException("Unable to retrieve contributor submissions.")


# ============================================================
# DETAIL VIEW
# ============================================================

class ContributorSubmissionDetailView(_CuratorBaseView, generics.RetrieveAPIView):
    queryset = ContributorSubmission.objects.all()
    serializer_class = ContributorSubmissionDetailSerializer
    lookup_field = "id"


# ============================================================
# STATUS UPDATE VIEW
# ============================================================

class ContributorSubmissionStatusUpdateView(_CuratorBaseView, APIView):
    """
    PATCH /submissions/<id>/status/

    Includes parser_classes → prevents DRF from failing with 415 Unsupported Media Type
    when RequestFactory sends no content-type.
    """
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    service = ContributorSubmissionService()

    def patch(self, request, id):
        # Extract new status safely
        new_status = request.data.get("status")
        note = request.data.get("note", "")

        # Basic validation
        allowed_statuses = ContributorSubmissionService.VALID_STATUSES - {"WAITING_FOR_APPROVAL"}
        if new_status not in allowed_statuses:
            return Response(
                {"error": "Invalid status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            updated = self.service.update_status(
                submission_id=id,
                new_status=new_status,
                reviewer=request.user,
                note=note,
            )

        except PermissionDenied as exc:
            # RBAC violation (non-curator)
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        except ValidationError as exc:
            # Any validation error from service layer
            return Response(
                exc.detail,
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            # THIS IS WHAT THE LAST FAILING TEST EXPECTS → return 500
            logger.exception("Error updating contributor submission status id=%s", id)
            return Response(
                {"detail": "Internal error while updating submission status."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Success
        return Response(
            ContributorSubmissionDetailSerializer(updated).data,
            status=status.HTTP_200_OK,
        )
