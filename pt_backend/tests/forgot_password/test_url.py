from django.test import TestCase
from django.urls import resolve, reverse
from pt_backend.views import PasswordResetLinkRequestView

class PasswordResetURLTests(TestCase):
    """Test the URL patterns for password reset functionality"""
    
    def test_password_reset_request_url_resolves(self):
        """Test that the password reset request URL resolves to the correct view"""
        url = reverse('password-reset-request')
        self.assertEqual(
            resolve(url).func.view_class,
            PasswordResetLinkRequestView
        )
    
    def test_password_reset_request_url_name(self):
        """Test the named URL for password reset request"""
        url = reverse('password-reset-request')
        self.assertEqual(url, '/api/auth/password-reset-request/')