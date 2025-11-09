from typing import Any
from .models import ExpertDataLog

def log_expert_action(user, *, data_id, title: str, note: str = "") -> None:
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
        # non-blocking
        pass
