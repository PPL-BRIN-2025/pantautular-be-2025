import hmac
import os
from typing import Iterable

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

class APIKeyAuthentication(BaseAuthentication):
   

    HEADER_NAME = "X-API-KEY"
    def authenticate(self, request):
        api_key = request.headers.get(self.HEADER_NAME)
        if not api_key:
            raise AuthenticationFailed("API key missing.")

        if not self._key_is_valid(api_key):
            raise AuthenticationFailed("Invalid API key.")
        return (AnonymousUser(), api_key)

    def authenticate_header(self, request):
        return f'{self.HEADER_NAME} realm="api"'

    def _get_expected_keys(self) -> Iterable[str]:
        keys = getattr(settings, "SECRET_API_KEYS", None)
        if keys:
            return keys
        env_key = os.getenv("SECRET_API_KEY")
        return (env_key,) if env_key else ()

    def _key_is_valid(self, candidate: str) -> bool:
        for expected in self._get_expected_keys():
            if expected and hmac.compare_digest(candidate, expected):
                return True
        return False
