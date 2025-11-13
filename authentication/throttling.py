from django.conf import settings
from rest_framework.throttling import AnonRateThrottle

class PasswordResetRateThrottle(AnonRateThrottle):
    """
    Throttle for password reset requests - limits by IP address.
    """
    scope = 'password_reset'
    
    def get_cache_key(self, request, view):
        return self.get_ident(request)

    def allow_request(self, request, view):
        if getattr(settings, "DISABLE_PASSWORD_RESET_THROTTLE", settings.DEBUG):
            return True
        return super().allow_request(request, view)
