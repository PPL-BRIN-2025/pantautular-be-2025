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
    DownloadLogRequestSerializer,
    DownloadLogResponseSerializer,
    DashboardDownloadEventSerializer,
)
from curator_feature.services import DownloadLogService

logger = logging.getLogger(__name__)


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
