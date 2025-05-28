"""
Custom middleware for security headers including Content Security Policy (CSP)
"""
import secrets
from django.conf import settings

class SecurityHeadersMiddleware:
    """
    Middleware to add security headers including Content Security Policy (CSP)
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Generate nonce for this request (if needed for inline scripts)
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce
        
        # Content Security Policy (CSP) - Strict Policy
        # This policy blocks inline scripts and eval() for better security
        csp_policy = self._build_csp_policy(nonce)
        
        # Use report-only mode in development, enforce in production
        if getattr(settings, 'CSP_REPORT_ONLY', False):
            response['Content-Security-Policy-Report-Only'] = csp_policy
        else:
            response['Content-Security-Policy'] = csp_policy
        
        # Additional security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response
    
    def _build_csp_policy(self, nonce):
        """
        Build CSP policy string with optional nonce support
        """
        # Base strict policy - no unsafe-inline or unsafe-eval
        policy_parts = [
            "default-src 'self'",
            "script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "style-src 'self' https://fonts.googleapis.com https://cdn.jsdelivr.net",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https:",
            "connect-src 'self' https://api.github.com",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
            "upgrade-insecure-requests"
        ]
        
        # Add nonce to script-src if needed (for emergency inline scripts)
        # Uncomment the line below if you need to allow specific inline scripts with nonces
        # policy_parts[1] += f" 'nonce-{nonce}'"
        
        # Add report-uri if configured
        report_uri = getattr(settings, 'CSP_REPORT_URI', None)
        if report_uri:
            policy_parts.append(f"report-uri {report_uri}")
        
        return "; ".join(policy_parts) 