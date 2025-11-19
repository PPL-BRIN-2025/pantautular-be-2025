from datetime import datetime, timezone
from pythonjsonlogger import jsonlogger


class StructuredJsonFormatter(jsonlogger.JsonFormatter):
    """Minimal JSON formatter that keeps useful fields and any extra context."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        # Preserve core fields even when not provided explicitly
        log_record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        log_record.setdefault("level", record.levelname)
        log_record.setdefault("logger", record.name)
        if "message" not in log_record:
            log_record["message"] = record.getMessage()  # pragma: no cover - defensive fallback
