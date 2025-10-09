import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from authentication.security import CustomJWTAuthentication
from authentication.permissions import IsTokenAuthenticated

from curator_feature.serializers import (
    DownloadLogRequestSerializer,
    DownloadLogResponseSerializer,
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
