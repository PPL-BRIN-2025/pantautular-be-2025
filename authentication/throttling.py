from rest_framework.throttling import AnonRateThrottle

class PasswordResetRateThrottle(AnonRateThrottle):
    """
    Throttle for password reset requests - limits by IP address.
    """
    scope = 'password_reset'
    
    def get_cache_key(self, request, view):
        return self.get_ident(request)