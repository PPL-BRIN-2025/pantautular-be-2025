import logging
from typing import Any

from django.db import DatabaseError, transaction

from curator_feature.models import DownloadLog

logger = logging.getLogger(__name__)


class DownloadLogService:
    """Encapsulate persistence logic for download logs."""

    def log_download(self, *, username: str, chart_type: str, timestamp: Any) -> DownloadLog:
        try:
            with transaction.atomic():
                return DownloadLog.objects.create(
                    username=username,
                    chart_type=chart_type,
                    timestamp=timestamp,
                )
        except DatabaseError as exc:
            logger.exception("Failed to persist download log for user=%s chart=%s", username, chart_type)
            raise
