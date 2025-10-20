from django.utils import timezone
from .models import CuratorDataLog

def log_curator_action(user, data_id, title=None, note=None):
    CuratorDataLog.objects.create(
        data_id=data_id,
        title=title or "N/A",
        submitted_by=(getattr(user, "username", "") or getattr(user, "email", ""))[:150],
        last_edited=timezone.now(),
        note=note or "",
    )
