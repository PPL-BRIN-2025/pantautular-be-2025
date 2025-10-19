import logging

from django.conf import settings
from django.shortcuts import render  # if unused, you can remove later

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsTokenAuthenticated
from authentication.security import CustomJWTAuthentication
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
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
)
from pt_backend.serializers import DiseaseSerializer
from curator_feature.services import (
    ChartDataService,
    DashboardDownloadEventService,
    DownloadLogService,
)
from curator_feature.value_objects import ClientMetadata
from pt_backend.models import Case
from .permissions import IsCuratorRole

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
from rest_framework import generics
from rest_framework.permissions import SAFE_METHODS


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