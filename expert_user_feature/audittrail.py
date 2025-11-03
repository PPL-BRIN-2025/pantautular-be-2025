from typing import Any, Dict

try:
    # Reuse curator's audit helper if available
    from curator_feature.audittrail import log_event as curator_log_event
except Exception:
    curator_log_event = None


def log_expert_event(user, action: str, meta: Dict[str, Any]) -> None:
    """
    Thin wrapper for logging audit events in expert_feature.
    Uses curator_feature.audittrail if available.
    """
    try:
        if curator_log_event:
            curator_log_event(user=user, action=action, meta=meta)
    except Exception:
        # Avoid blocking core logic if audit fails
        pass
