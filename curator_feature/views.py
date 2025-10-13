import logging
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from authentication.security import CustomJWTAuthentication
from authentication.permissions import IsTokenAuthenticated
from pt_backend.authentication import APIKeyAuthentication

from curator_feature.models import DashboardDownloadEvent
from curator_feature.serializers import (
    ChartDataFiltersSerializer,
    DownloadLogRequestSerializer,
    DownloadLogResponseSerializer,
    DashboardDownloadEventSerializer,
)
from curator_feature.services import ChartDataService, DownloadLogService

logger = logging.getLogger(__name__)

from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import CuratorDataLog, BackendCase
from .serializers import CuratorDataLogSerializer
from .permissions import IsCuratorRole

class CuratorDataLogListCreateAPIView(APIView):
    """
    GET /curator-feature/api/curator/audit-logs/
      ?page=1&pageSize=10&search=&start=&end=&submitted_by=&sort=last_edited:desc

    POST /curator-feature/api/curator/audit-logs/
      { "data_id": "<uuid>", "title": "hospitalisasi", "note": "optional" }
    """
    permission_classes = [IsAuthenticated, IsCuratorRole]

    def get(self, request):
        # pagination
        def _i(v, d=None):
            try: return int(v)
            except: return d
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
                Q(title__icontains=search) |
                Q(submitted_by__icontains=search) |
                Q(data_id__icontains=search)
            )
        if submitted_by:
            qs = qs.filter(submitted_by__icontains=submitted_by)
        if start:
            qs = qs.filter(last_edited__gte=start)
        if end:
            qs = qs.filter(last_edited__lte=end)

        total = qs.count()
        items = qs.order_by(order_by)[(page-1)*page_size : page*page_size]
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

        payload["submittedBy"] = getattr(request.user, "username", "") or getattr(request.user, "email", "")
        ser = CuratorDataLogSerializer(data=payload)
        if ser.is_valid():
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
      
class ChartsSimpleView(APIView):
    def get(self, request, *args, **kwargs):
        from curator_feature.services import ChartDataService
        service = ChartDataService()
        try:
            payload = service.get_chart_data()
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

        filters = self._build_filters(serializer.validated_data)
        try:
            payload = self.service.get_chart_data(filters=filters or None)
        except Exception:
            logger.exception("Unable to retrieve chart data with filters")
            return Response(
                {"message": "Failed to fetch chart data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(payload, status=status.HTTP_200_OK)

    def _build_filters(self, data):
        filters = {}
        diseases = data.get("diseases") or []
        if diseases:
            filters["disease"] = diseases

        portals = data.get("portals") or []
        if portals:
            filters["portals"] = portals

        level = data.get("level_of_alertness")
        if level:
            filters["disease_alertness"] = level

        locations = data.get("locations") or {}
        provinces = locations.get("provinces") or []
        cities = locations.get("cities") or []
        if provinces:
            filters["provinces"] = provinces
        if cities:
            filters["cities"] = cities

        start_date = data.get("start_date")
        end_date = data.get("end_date")
        if start_date or end_date:
            filters["date_range"] = {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            }

        return filters


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

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        if not getattr(settings, "ENABLE_DOWNLOAD_LOGGING", False):
            return Response(
                {"logged": False, "detail": "Download logging disabled"},
                status=status.HTTP_202_ACCEPTED,
            )

        metadata = {}
        filters = payload.get("filters")
        if filters:
            metadata["filters"] = filters
        source = payload.get("source")
        if source:
            metadata["source"] = source

        event = DashboardDownloadEvent.objects.create(
            metric=payload["metric"],
            file_format=payload["file_format"],
            metadata=metadata or None,
            client_ip=self._extract_client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:512],
        )

        return Response({"id": event.id, "logged": True}, status=status.HTTP_201_CREATED)

    def _extract_client_ip(self, request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

