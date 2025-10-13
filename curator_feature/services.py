from django.utils import timezone
from .models import CuratorDataLog

def log_curator_edit(*, user, data_id, title=None, note=None):
    """
    Create a CuratorDataLog row.
    title can be severity (recommended).
    """
    CuratorDataLog.objects.create(
        data_id=data_id,
        title=title or "N/A",
        submitted_by=(getattr(user, "username", "") or getattr(user, "email", ""))[:150],
        last_edited=timezone.now(),
        note=note or "",
    )
