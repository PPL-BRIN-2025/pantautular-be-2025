import logging

from django.conf import settings
from django.shortcuts import render  # if unused, you can remove later
import logging

from django.conf import settings
from django.shortcuts import render  # if unused, you can remove later
from django.db.models import Q

from rest_framework.exceptions import ValidationError, PermissionDenied, APIException
from rest_framework import generics, status
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
from pt_backend.models import Case
from .permissions import IsCuratorRole

# models for audit logs
from .models import CuratorDataLog, BackendCase, ContributorSubmission

logger = logging.getLogger(__name__)


# ===============================
# Charts & Downloads APIs
# ===============================
class ChartsSimpleView(APIView):
    service_class = ChartDataService

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = self.service_class()

    def get(self, request, *args, **kwargs):
        try:
            payload = self.service.get_chart_data()
        except Exception:
            logger.exception("Unable to retrieve chart data from pt_backend")
            return Response({"message": "Failed to fetch chart data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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
        try:
            payload = self.service.get_chart_data(filters=None)
        except Exception:
            logger.exception("Unable to retrieve chart data")
            return Response(
                {"message": "Failed to fetch chart data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = self.request_serializer_class(data=request.data)
        if not serializer.is_valid():
            logger.debug("Invalid chart data filters: %s", serializer.errors)
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        filters = serializer.to_filters()
        try:
            payload = self.service.get_chart_data(filters=filters or None)
        except Exception:
            logger.exception("Unable to retrieve chart data with filters")
            return Response(
                {"message": "Failed to fetch chart data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
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
        serializer = self.request_serializer_class(data=request.data)
        if not serializer.is_valid():
            logger.debug("Invalid download log payload: %s", serializer.errors)
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data

        if not getattr(settings, "ENABLE_DOWNLOAD_LOGGING", False):
            return Response(
                {"logged": False, "detail": "Download logging disabled"},
                status=status.HTTP_202_ACCEPTED,
            )

        try:
            log_entry = self.service.log_download(
                username=payload["username"],
                chart_type=payload["chartType"],
                timestamp=payload["timestamp"],
            )
        except Exception:
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

        if not getattr(settings, "ENABLE_DOWNLOAD_LOGGING", False):
            return Response(
                {"logged": False, "detail": "Download logging disabled"},
                status=status.HTTP_202_ACCEPTED,
            )

        client_metadata = ClientMetadata.from_request(request)
        event = self.service.log_event(
            metric=payload["metric"],
            file_format=payload["file_format"],
            filters=payload.get("filters"),
            source=payload.get("source"),
            client=client_metadata,
        )

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


# ===============================
# Curator Audit Logs API
# ===============================
class CuratorDataLogListCreateAPIView(APIView):
    authentication_classes = [CustomJWTAuthentication, SessionAuthentication]
    permission_classes = [IsTokenAuthenticated, IsCuratorRole] 

    def get(self, request):
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

        total = qs.count()
        items = qs.order_by(order_by)[(page - 1) * page_size : page * page_size]
        data = CuratorDataLogSerializer(items, many=True).data

        return Response(
            {"data": data, "page": page, "pageSize": page_size, "total": total},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        # optional helper endpoint to create a log
        payload = request.data.copy()
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
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)



logger = logging.getLogger(__name__)


# ============================================================
# LIST VIEW
# ============================================================

class ContributorSubmissionListView(_CuratorBaseView, generics.ListAPIView):
    """
    GET /submissions/
      ?search=<optional text>
      ?status=<optional status>
    """
    serializer_class = ContributorSubmissionListSerializer
    service = ContributorSubmissionService()

    def get_queryset(self):
        search = (self.request.query_params.get("search") or "").strip()
        status_param = (self.request.query_params.get("status") or "").strip() or None

        try:
            return self.service.list(search=search, status=status_param)
        except Exception:
            logger.exception("Unable to retrieve contributor submissions")
            raise APIException("Unable to retrieve contributor submissions.")


# ============================================================
# DETAIL VIEW
# ============================================================

class ContributorSubmissionDetailView(_CuratorBaseView, generics.RetrieveAPIView):
    """
    GET /submissions/<id>/
    """
    queryset = ContributorSubmission.objects.all()
    serializer_class = ContributorSubmissionDetailSerializer
    lookup_field = "id"


# ============================================================
# STATUS UPDATE VIEW (APPROVE / REJECT / REVISION)
# ============================================================

class ContributorSubmissionStatusUpdateView(_CuratorBaseView, APIView):
    """
    PATCH /submissions/<id>/status/
    """
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    service = ContributorSubmissionService()

    def patch(self, request, id):
        raw_status = request.data.get("status") or ""
        new_status = str(raw_status).strip().upper()
        note = (request.data.get("note") or "").strip()
        allowed_statuses = (
            ContributorSubmissionService.VALID_STATUSES - {"WAITING_FOR_APPROVAL"}
        )
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
            return Response(
                exc.detail,
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            # Fallback 500 
            logger.exception("Error updating contributor submission status id=%s", id)
            return Response(
                {"detail": "Internal error while updating submission status."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        data = ContributorSubmissionDetailSerializer(updated).data
        return Response(data, status=status.HTTP_200_OK)


# ============================================================
# MARK SEEN VIEW (KONTRIBUTOR SUDAH LIHAT UPDATE)
# ============================================================

class ContributorSubmissionMarkSeenView(_CuratorBaseView, APIView):
    """
    PATCH /submissions/<id>/mark-seen/
    """
    service = ContributorSubmissionService()

    def patch(self, request, id):
        try:
            # query model directly so we know exactly what exception we get
            sub = ContributorSubmission.objects.get(id=id)
        except ContributorSubmission.DoesNotExist:
            # clean 404 when submission doesn't exist
            return Response(
                {"detail": "Submission not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            # any other unexpected error → 500
            logger.exception(
                "Error fetching submission for mark-seen id=%s", id
            )
            return Response(
                {"detail": "Internal error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # reset flag only if it was previously True
        if sub.has_unseen_update:
            sub.has_unseen_update = False
            sub.save(update_fields=["has_unseen_update"])

        return Response({"seen": True}, status=status.HTTP_200_OK)
