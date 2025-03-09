from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
import os

class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        api_key = request.headers.get("X-API-KEY")  
        secret_key = os.getenv("SECRET_API_KEY")

        if not api_key or api_key != secret_key:
            raise AuthenticationFailed("Invalid API Key")

        return (None, None)  
