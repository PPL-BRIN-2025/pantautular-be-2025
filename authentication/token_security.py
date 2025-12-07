import logging
import threading
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied


logger = logging.getLogger("pantau_tular.access_control")


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    return max(1, result)


def _get_default_rate_limit() -> Dict[str, int]:
    config = getattr(settings, "API_TOKEN_DEFAULT_RATE_LIMIT", None) or {}
    return {
        "requests": _coerce_positive_int(config.get("requests"), 100),
        "window": _coerce_positive_int(config.get("window"), 60),
    }


def _get_block_duration() -> int:
    value = getattr(settings, "API_TOKEN_BLOCK_DURATION", 300)
    return _coerce_positive_int(value, 300)


def _mask_token_value(token_value: Optional[str]) -> str:
    if not token_value:
        return "unknown"
    if len(token_value) <= 4:
        return "***"
    return f"{token_value[:4]}***"


class RateLimitExceeded(Exception):
    """Raised when a token exceeds its configured rate limit."""

    def __init__(self, max_requests: int, retry_after: int, blocked: bool = True):
        self.max_requests = max_requests
        self.retry_after = max(1, int(retry_after))
        self.blocked = blocked
        self.detail = f"Rate limit exceeded. Maximum {max_requests} requests allowed."
        super().__init__(self.detail)


class RateLimiter:
    """Thread-safe, in-memory rate limiter with per-token overrides and blocking."""

    def __init__(self) -> None:
        self._state: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._time_provider: Optional[Any] = None

    def _now(self):
        provider = self._time_provider
        if provider:
            return provider()
        return timezone.now()

    def set_time_provider(self, provider) -> None:
        """Used in tests to control the perceived current time."""
        with self._lock:
            self._time_provider = provider

    def clear_time_provider(self) -> None:
        with self._lock:
            self._time_provider = None

    def reset(self, token_key: Optional[str] = None) -> None:
        with self._lock:
            if token_key is None:
                self._state.clear()
            else:
                self._state.pop(token_key, None)

    def _resolve_limits(self, custom_limit: Optional[Dict[str, Any]]):
        defaults = _get_default_rate_limit()
        effective = custom_limit or {}
        requests_allowed = _coerce_positive_int(effective.get("requests"), defaults["requests"])
        window_seconds = _coerce_positive_int(effective.get("window"), defaults["window"])
        block_seconds = _get_block_duration()
        return requests_allowed, window_seconds, block_seconds

    def enforce(self, token_key: str, custom_limit: Optional[Dict[str, Any]] = None, context: Optional[Dict[str, Any]] = None) -> None:
        """Validate and record the token request. Raises RateLimitExceeded if blocked."""
        context = context or {}
        requests_allowed, window_seconds, block_seconds = self._resolve_limits(custom_limit)
        now = self._now()
        with self._lock:
            state = self._state.setdefault(
                token_key,
                {"count": 0, "window_start": now, "blocked_until": None},
            )

            blocked_until = state.get("blocked_until")
            if blocked_until and now < blocked_until:
                wait = int((blocked_until - now).total_seconds())
                logger.warning(
                    "Blocked request for token=%s from ip=%s path=%s, %ss cooldown remaining",
                    _mask_token_value(token_key),
                    context.get("ip", "unknown"),
                    context.get("path", ""),
                    wait,
                )
                raise RateLimitExceeded(max_requests=requests_allowed, retry_after=wait)

            if blocked_until and now >= blocked_until:
                state["count"] = 0
                state["blocked_until"] = None
                state["window_start"] = now

            window_start = state["window_start"]
            if (now - window_start).total_seconds() >= window_seconds:
                state["count"] = 0
                state["window_start"] = now

            state["count"] += 1
            if state["count"] > requests_allowed:
                state["count"] = requests_allowed
                blocked_until = now + timedelta(seconds=block_seconds)
                state["blocked_until"] = blocked_until
                logger.warning(
                    "Rate limit exceeded for token=%s from ip=%s path=%s, blocking for %ss",
                    _mask_token_value(token_key),
                    context.get("ip", "unknown"),
                    context.get("path", ""),
                    block_seconds,
                )
                raise RateLimitExceeded(max_requests=requests_allowed, retry_after=block_seconds)


class RateLimitAPIException(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "rate_limited"

    def __init__(self, detail: str, retry_after: Optional[int] = None):
        payload: Dict[str, Any] = {"detail": detail}
        if retry_after is not None:
            payload["retry_after"] = max(1, int(retry_after))
        super().__init__(payload)
        if isinstance(self.detail, dict) and "retry_after" in payload:
            self.detail["retry_after"] = payload["retry_after"]


class TokenAuthError(Exception):
    def __init__(self, message: str, *, code: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass
class APIConsumer:
    token: str
    name: str
    permissions: Any
    metadata: Dict[str, Any]

    @property
    def is_authenticated(self) -> bool:
        return True


class TokenAuth:
    """Validates configured API tokens and their constraints."""

    def __init__(self, tokens: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self._tokens = tokens

    @property
    def tokens(self) -> Dict[str, Dict[str, Any]]:
        return (self._tokens if self._tokens is not None else getattr(settings, "API_TOKENS", {})) or {}

    def _mask_token(self, token_value: str) -> str:
        return _mask_token_value(token_value)

    def resolve(self, raw_token: Optional[str], context: Optional[Dict[str, Any]] = None):
        context = context or {}
        token_value = (raw_token or "").strip()
        path = context.get("path", "")
        if not token_value:
            logger.warning("Missing API token for %s from ip=%s", path, context.get("ip", "unknown"))
            raise TokenAuthError("API token required", code="missing")
        token = self.tokens.get(token_value)
        if not token:
            logger.warning(
                "Invalid API token attempt (%s) for %s from ip=%s",
                self._mask_token(token_value),
                path,
                context.get("ip", "unknown"),
            )
            raise TokenAuthError("API token required", code="invalid")
        return token_value, token

    def ensure_ip_allowed(self, token_key: str, token_config: Dict[str, Any], remote_addr: str) -> None:
        allowed_ips = token_config.get("allowed_ips") or []
        client_ip = remote_addr or "unknown"
        if allowed_ips and client_ip not in allowed_ips:
            logger.warning(
                "IP whitelist violation for token=%s from ip=%s allowed=%s",
                self._mask_token(token_key),
                client_ip,
                allowed_ips,
            )
            raise TokenAuthError("IP not authorized", code="ip_not_authorized")

    def build_principal(self, token_key: str, token_config: Dict[str, Any], remote_addr: str) -> APIConsumer:
        permissions = token_config.get("permissions") or []
        metadata = {
            "ip": remote_addr,
            "scope": permissions,
        }
        return APIConsumer(
            token=token_key,
            name=token_config.get("name") or "API Consumer",
            permissions=permissions,
            metadata=metadata,
        )


class AccessTokenAuthentication(BaseAuthentication):
    """DRF authentication class that enforces token validation, IP checking, and rate limiting."""

    header = "X-API-TOKEN"

    def __init__(self) -> None:
        self.token_auth = TokenAuth()
        self.rate_limiter = rate_limiter

    def authenticate(self, request):
        token_value = self._extract_token(request)
        remote_addr = self._get_remote_addr(request)
        context = {
            "ip": remote_addr,
            "path": request.get_full_path() if hasattr(request, "get_full_path") else "",
        }
        try:
            token_key, token_config = self.token_auth.resolve(token_value, context=context)
            self.token_auth.ensure_ip_allowed(token_key, token_config, remote_addr)
            self.rate_limiter.enforce(token_key, token_config.get("rate_limit"), context=context)
        except TokenAuthError as exc:
            if exc.code == "ip_not_authorized":
                raise PermissionDenied(detail=str(exc))
            raise AuthenticationFailed(detail=str(exc))
        except RateLimitExceeded as exc:
            raise RateLimitAPIException(detail=exc.detail, retry_after=exc.retry_after)

        principal = self.token_auth.build_principal(token_key, token_config, remote_addr)
        return (principal, token_key)

    def authenticate_header(self, request):
        return self.header

    def _extract_token(self, request) -> Optional[str]:
        header_value = request.headers.get(self.header)
        if header_value:
            return header_value.strip()
        authorization = request.headers.get("Authorization")
        if authorization:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "token":
                return parts[1].strip()
        return None

    def _get_remote_addr(self, request) -> str:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR") or "unknown"


rate_limiter = RateLimiter()

__all__ = [
    "APIConsumer",
    "AccessTokenAuthentication",
    "RateLimitAPIException",
    "RateLimitExceeded",
    "RateLimiter",
    "TokenAuth",
    "rate_limiter",
]
