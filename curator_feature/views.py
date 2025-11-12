import logging
from datetime import datetime, time

from django.conf import settings
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
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
)
from pt_backend.serializers import DiseaseSerializer
from curator_feature.services import (
    ChartDataService,
    DashboardDownloadEventService,
    DownloadLogService,
)
from curator_feature.value_objects import ClientMetadata
from pt_backend.models import Case, User as PtUser
from .permissions import IsCuratorRole

# models for audit logs
from .models import CuratorDataLog, BackendCase

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
    DEFAULT_PAGE_SIZE = 25
    MAX_PAGE_SIZE = 100
    SORT_FIELD_MAP = {
        "age": "age",
        "city": "city",
        "gender": "gender",
        "status": "status",
        "severity": "severity",
        "id": "id",
    }

    def get_serializer_class(self):
        return CaseReadSerializer if self.request.method == "GET" else CaseWriteSerializer

    def list(self, request, *args, **kwargs):
        params = request.query_params
        page = self._parse_positive_int(params.get("page"), default=1)
        page_size = self._parse_positive_int(params.get("pageSize"), default=self.DEFAULT_PAGE_SIZE)
        page_size = min(self.MAX_PAGE_SIZE, max(1, page_size))
        offset = (page - 1) * page_size

        user = getattr(request, "user", None)
        prefer_case_queryset = isinstance(user, PtUser)
        queryset = self.filter_queryset(self.get_queryset())
        has_case_data = prefer_case_queryset and queryset.exists()

        if has_case_data:
            total = queryset.count()
            items = queryset[offset : offset + page_size]
            serializer = CaseReadSerializer(items, many=True, context={"request": request})
            data = serializer.data
        else:
            backend_queryset = self._build_backend_case_queryset(params)
            if backend_queryset.exists():
                data, total = self._serialize_backend_cases(params, offset, page_size, backend_queryset)
            else:
                total = queryset.count()
                items = queryset[offset : offset + page_size]
                serializer = CaseReadSerializer(items, many=True, context={"request": request})
                data = serializer.data

        payload = {
            "data": data,
            "total": total,
            "page": page,
            "pageSize": page_size,
        }
        return Response(payload, status=status.HTTP_200_OK)

    def _build_backend_case_queryset(self, params):
        queryset = BackendCase.objects.all()

        search = (params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(city__icontains=search)
                | Q(status__icontains=search)
                | Q(severity__icontains=search)
            )

        def _normalize_str(value):
            return value.strip() if isinstance(value, str) else value

        gender = _normalize_str(params.get("gender"))
        if gender:
            queryset = queryset.filter(gender__iexact=gender)

        status_filter = _normalize_str(params.get("status"))
        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)

        severity = _normalize_str(params.get("severity"))
        if severity:
            queryset = queryset.filter(severity__iexact=severity)

        location_id = _normalize_str(params.get("location_id"))
        if location_id:
            queryset = queryset.filter(location_id=location_id)

        disease_id = _normalize_str(params.get("disease_id"))
        if disease_id:
            queryset = queryset.filter(disease_id=disease_id)

        min_age = self._parse_positive_int(params.get("minAge"))
        if min_age is not None:
            queryset = queryset.filter(age__gte=min_age)

        max_age = self._parse_positive_int(params.get("maxAge"))
        if max_age is not None:
            queryset = queryset.filter(age__lte=max_age)

        sort_expression = self._resolve_sort(params.get("sort"))
        return queryset.order_by(sort_expression)

    def _resolve_sort(self, raw_sort):
        if raw_sort:
            parts = raw_sort.split(":")
            field = parts[0].strip().lower()
            direction = (parts[1] if len(parts) > 1 else "asc").strip().lower()
        else:
            field = "id"
            direction = "desc"

        mapped_field = self.SORT_FIELD_MAP.get(field)
        if not mapped_field:
            mapped_field = self.SORT_FIELD_MAP["id"]
            direction = "desc"

        prefix = "-" if direction == "desc" else ""
        return f"{prefix}{mapped_field}"

    @staticmethod
    def _parse_positive_int(value, default=None):
        if value in (None, ""):
            return default
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except (TypeError, ValueError):
            return default

    def _serialize_backend_cases(self, params, offset, page_size, queryset=None):
        queryset = queryset or self._build_backend_case_queryset(params)
        total = queryset.count()
        items = queryset[offset : offset + page_size]
        data = [
            {
                "id": str(item.id),
                "gender": item.gender,
                "age": item.age,
                "city": item.city,
                "status": item.status,
                "severity": item.severity,
                "disease_id": str(item.disease_id) if item.disease_id else None,
                "location_id": str(item.location_id) if item.location_id else None,
            }
            for item in items
        ]
        return data, total

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
    authentication_classes = [CustomJWTAuthentication, SessionAuthentication, BasicAuthentication]
    permission_classes = [IsTokenAuthenticated, IsCuratorRole] 
    _DATE_INPUT_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y")

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
        submitted_by = (
            request.query_params.get("submitted_by")
            or request.query_params.get("submittedBy")
            or request.query_params.get("submittedby")
            or request.query_params.get("curator")
            or ""
        ).strip()

        start_raw = self._first_query_value(
            request,
            "start",
            "startDate",
            "start_date",
            "from",
            "date_start",
        )
        end_raw = self._first_query_value(
            request,
            "end",
            "endDate",
            "end_date",
            "to",
            "date_end",
        )
        single_date_raw = None
        if not start_raw and not end_raw:
            single_date_raw = self._first_query_value(
                request,
                "date",
                "dateFilter",
                "lastEdited",
                "last_edited",
            )

        single_day_range = self._parse_single_day_range(single_date_raw) if single_date_raw else (None, None)
        if single_day_range != (None, None):
            start, end = single_day_range
        else:
            start = self._parse_datetime_param(start_raw)
            end = self._parse_datetime_param(end_raw, clamp_end=True)

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
        if start is not None:
            qs = qs.filter(last_edited__gte=start)
        if end is not None:
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

    @staticmethod
    def _first_query_value(request, *keys):
        for key in keys:
            value = request.query_params.get(key)
            if value:
                value = value.strip()
                if value:
                    return value
        return None

    @classmethod
    def _parse_datetime_param(cls, value, *, clamp_end=False):
        if not value:
            return None

        parsed = parse_datetime(value)
        if not parsed:
            parsed_date = cls._parse_date_only(value)
            if parsed_date:
                target_time = time.max if clamp_end else time.min
                parsed = datetime.combine(parsed_date, target_time)

        if not parsed:
            return None

        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    @classmethod
    def _parse_date_only(cls, value):
        for fmt in cls._DATE_INPUT_FORMATS:
            try:
                return datetime.strptime(value, fmt).date()
            except (ValueError, TypeError):
                continue
        return None

    @classmethod
    def _parse_single_day_range(cls, value):
        if not value:
            return (None, None)

        parsed = parse_datetime(value)
        if parsed:
            if timezone.is_naive(parsed):
                tz = timezone.get_current_timezone()
                parsed = timezone.make_aware(parsed, tz)
            target_tz = parsed.tzinfo or timezone.get_current_timezone()
            return cls._build_day_range(parsed.date(), target_tz)

        parsed_date = cls._parse_date_only(value)
        if parsed_date:
            return cls._build_day_range(parsed_date, tz)
        return (None, None)

    @staticmethod
    def _build_day_range(day, tz):
        start = timezone.make_aware(datetime.combine(day, time.min), tz)
        end = timezone.make_aware(datetime.combine(day, time.max), tz)
        return start, end
