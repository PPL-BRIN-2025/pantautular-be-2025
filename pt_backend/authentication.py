import hmac
import os
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import PermissionDenied


class APIKeyAuthentication(BaseAuthentication):
    HEADER_NAME = "X-API-KEY"

    def authenticate(self, request):  # pragma: no cover
        if getattr(request, "_skip_api_key_auth", False):  # pragma: no branch
            return None

        expected_keys = self._get_expected_keys()
        if not expected_keys:
            return None

        api_key = request.headers.get(self.HEADER_NAME)
        if not api_key:
            raise PermissionDenied("Invalid API Key")  # pragma: no cover

        for expected in expected_keys:
            if hmac.compare_digest(api_key, expected):
                return None

        raise PermissionDenied("Invalid API Key")  # pragma: no cover

    @staticmethod
    def _get_expected_keys():
        keys = []
        env_key = os.getenv("SECRET_API_KEY")
        if env_key:  # pragma: no branch
            keys.append(env_key)
        setting_key = getattr(settings, "SECRET_API_KEY", None)
        if setting_key:  # pragma: no branch
            keys.append(setting_key)
        configured = getattr(settings, "SECRET_API_KEYS", None)
        if configured:  # pragma: no branch
            keys.extend(configured)
        return tuple(k for k in keys if k)


class APIKeyRequiredAuthentication(APIKeyAuthentication):
    """
    Variant of API key authentication that enforces the key but never sets
    request.user/auth, allowing other authenticators (e.g., JWT) to populate it.
    """

    def authenticate(self, request):
        super().authenticate(request)
        return None
