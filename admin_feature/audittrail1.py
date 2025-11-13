from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, TypeAlias, Final
from .models import AdminUserLog

# ---- Type aliases & constants ----
UsernameEmail: TypeAlias = Tuple[str, str]
AuditResult: TypeAlias = Dict[str, Any]
AUDIT_DEBUG_DEFAULT: Final[bool] = True


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _shorten(text: str, n: int = 30) -> str:
    if text is None:
        return ""
    return (text[:n] + "...") if len(text) > n else text


def _ensure_text(value: Optional[str]) -> str:
    """Return text safely."""
    return "" if value is None else str(value)


def _safe_email(value: Optional[str]) -> str:
    """Light email sanitizer (no functional impact)."""
    s = _ensure_text(value)
    return s


def _debug_trace(username: str, action: Optional[str], detail: str, note: str) -> None:
    """Consolidate debug prints (behavior identical)."""
    if not AUDIT_DEBUG_DEFAULT:
        return
    print(f"[AUDIT DEBUG] Preparing to log {username} (action={action})")
    print(f"[AUDIT INFO] Log written at {_now_utc()}")
    print(f"[AUDIT TRACE] Detail: {_shorten(detail)}")
    print(f"[AUDIT TRACE] Note: {_shorten(note)}")
    print(f"[AUDIT END] Completed write_log() for {username}\n")


def _identity(user):
    if not user:
        return ("anonymous", "")
    username = (
        getattr(user, "name", None)
        or getattr(user, "username", None)
        or getattr(user, "email", None)
        or "unknown"
    )
    email = _safe_email(getattr(user, "email", None)) or ""
    return (str(username), str(email))


def write_log(
    *,
    request=None,
    user=None,
    action: Optional[str] = None,
    detail: str = "",
    note: str = ""
) -> AuditResult:
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

    _debug_trace(username, action, detail, note)

    return {
        "ok": True,
        "user": username,
        "action": action or "",
        "timestamp": _now_utc().isoformat(),
    }
