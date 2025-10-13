from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, TypeAlias, Final
from .models import AdminUserLog

# ---- Module-level type aliases and constants ----
UsernameEmail: TypeAlias = Tuple[str, str]
AuditResult: TypeAlias = Dict[str, Any]
AUDIT_DEBUG_DEFAULT: Final[bool] = True


def _now_utc() -> datetime:
    """Return timezone-aware UTC time."""
    return datetime.now(timezone.utc)


def _shorten(text: str, n: int = 30) -> str:
    """Preview text without changing logic."""
    if text is None:
        return ""
    return (text[:n] + "...") if len(text) > n else text


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
) -> AuditResult:
    """Write a simple admin audit log entry (core behavior unchanged)."""
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
        timestamp=_now_utc(),
    )

    print(f"[AUDIT DEBUG] Creating log for {username} (action={action})")
    print(f"[AUDIT INFO] Log written at {_now_utc()}")
    print(f"[AUDIT TRACE] Detail: {detail[:30]}...")
    print(f"[AUDIT TRACE] Note: {note[:30]}...")
    print(f"[AUDIT END] Done writing log for {username}\n")

    return {
        "ok": True,
        "user": username,
        "action": action or "",
        "timestamp": _now_utc().isoformat(),
    }
