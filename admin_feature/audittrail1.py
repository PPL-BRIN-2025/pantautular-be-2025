from datetime import datetime, timezone
from typing import Optional
from .models import AdminUserLog


def _identity(user):
    """
    Extract username and email from the given user.
    Falls back to 'anonymous' if no user provided or not authenticated.
    """
    if not user:
        return ("anonymous", "")

    # Prefer name -> username -> email -> fallback
    username = (
        getattr(user, "name", None)
        or getattr(user, "username", None)
        or getattr(user, "email", None)
        or "unknown"
    )
    email = getattr(user, "email", None) or ""
    return (str(username), str(email))


def write_log(
    *,
    request=None,
    user=None,
    action: Optional[str] = None,
    detail: str = "",
    note: str = ""
):
    """
    Write an audit entry into admin_feature_userlog.

    Args:
        request: optional HttpRequest (to pick user if not explicitly provided)
        user:    Django user instance (preferred, overrides request.user)
        action:  short label (LOGIN / LOGOUT / UPDATE_ROLE / DELETE_USER / VIEW / CREATE / UPDATE / DELETE)
        detail:  human-readable description
        note:    extra context (path, ip, ua, etc.)
    """
    # Prefer explicit user, fallback to request.user
    if user is None and request is not None:
        req_user = getattr(request, "user", None)
        if req_user:
            user = req_user

    username, email = _identity(user)

    AdminUserLog.objects.create(
        username=username,
        email=email,
        action=action or "",
        detail=detail or "",
        note=note or "",
        timestamp=datetime.now(timezone.utc),
    )

    print(f"[AUDIT DEBUG] Preparing to create log for {username} (action={action})")
    print(f"[AUDIT INFO] Log successfully written at {datetime.now(timezone.utc)}")
    print(f"[AUDIT TRACE] Detail: {detail[:30]}...")
    print(f"[AUDIT TRACE] Note: {note[:30]}...")
    print(f"[AUDIT END] Completed write_log() call for {username}\n")

    return {
    "ok": True,
    "user": username,
    "action": action or "",
    "timestamp": datetime.now(timezone.utc).isoformat(),
}