import logging
from typing import Any, Dict

from .models import ExpertDataLog

logger = logging.getLogger(__name__)

try:
    from curator_feature.audittrail import curator_log_event as _curator_log_event  # type: ignore
except Exception:  # pragma: no cover - fallback when curator feature unavailable
    _curator_log_event = None


def curator_log_event(**kwargs):
    """
    Compatibility shim so existing patches (see tests) can hook into curator logging.
    """
    if _curator_log_event:
        return _curator_log_event(**kwargs)
    return None


def log_expert_event(user: Any, action: str, meta: Dict[str, Any]):
    """
    Proxy expert events into curator audit trail, but swallow failures.
    """
    try:
        curator_log_event(user=user, action=action, feature="expert_user_feature", meta=meta)
    except Exception:
        logger.debug("expert_user_feature.log_expert_event swallowed error", exc_info=True)


def log_expert_action(user, *, data_id, title: str, note: str = "") -> None:
    """
    Persist immutable ExpertDataLog rows for EXP actions (upload/delete/etc).
    """
    try:
        submitted_by = (
            getattr(user, "email", None)
            or getattr(user, "username", None)
            or "unknown"
        )[:150]
        ExpertDataLog.objects.create(
            data_id=data_id, title=title, submitted_by=submitted_by, note=note
        )
    except Exception:
        logger.debug("Failed to persist expert data log", exc_info=True)
