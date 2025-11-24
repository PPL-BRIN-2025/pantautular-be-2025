import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

try:  # pragma: no cover - optional dependency in tests
    import sentry_sdk
except Exception:  # pragma: no cover
    sentry_sdk = None


monitoring_logger = logging.getLogger("pantautular.monitoring")
RESERVED_LOG_KEYS = {
    "filename",
    "module",
    "funcName",
    "lineno",
    "pathname",
    "process",
    "processName",
    "thread",
    "threadName",
    "name",
    "message",
    "asctime",
    "created",
    "msecs",
    "relativeCreated",
    "levelname",
    "levelno",
}


def _clean_context(data: Dict[str, Any]) -> Dict[str, Any]:
    """Drop keys with None values to keep logs compact."""
    cleaned: Dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        safe_key = key if key not in RESERVED_LOG_KEYS else f"ctx_{key}"
        cleaned[safe_key] = value
    return cleaned


def log_event(event: str, level: int = logging.INFO, **context: Any) -> None:
    payload = {"event": event, **_clean_context(context)}
    monitoring_logger.log(level, event, extra=payload)


@contextmanager
def record_duration(
    event: str,
    threshold_ms: Optional[float] = None,
    warn_message: Optional[str] = None,
    **context: Any,
):
    """
    Context manager to measure duration, log structured payloads, and send slow warnings to Sentry.
    """
    start = time.perf_counter()
    try:
        yield
    except Exception as exc:
        log_event(f"{event}.error", logging.ERROR, status="error", **context)
        if sentry_sdk:  # pragma: no cover - exercised in integration envs
            sentry_sdk.capture_exception(exc)
        raise
    else:
        duration_ms = (time.perf_counter() - start) * 1000
        payload = {"duration_ms": round(duration_ms, 2), **context}
        log_event(f"{event}.duration", logging.INFO, **payload)
        if threshold_ms and duration_ms > threshold_ms:  # pragma: no cover - exercised in perf environments
            log_event(
                f"{event}.slow",
                logging.WARNING,
                status="slow",
                threshold_ms=threshold_ms,
                **payload,
            )
            if sentry_sdk:  # pragma: no cover - exercised in integration envs
                sentry_sdk.capture_message(
                    warn_message or f"{event} slower than {threshold_ms}ms",
                    level="warning",
                )
