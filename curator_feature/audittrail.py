# curator_feature/audittrail.py
from django.utils import timezone
from .models import CuratorDataLog

def log_curator_action(user, data_id, title=None, note=None):
    """
    Log a curator's action into curator_feature_datalog.

    Args:
        user: request.user (curator)
        data_id: UUID of the related pt_backend_case
        title: e.g., severity or a short title
        note: optional description/context
    """
    CuratorDataLog.objects.create(
        data_id=data_id,
        title=title or "N/A",
        submitted_by=(getattr(user, "username", "") or getattr(user, "email", ""))[:150],
        last_edited=timezone.now(),
        note=note or "",
    )
