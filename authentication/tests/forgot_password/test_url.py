from django.test import TestCase
from django.urls import resolve, reverse
from authentication.views import PasswordResetLinkRequestView, PasswordResetLinkValidateView

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
        self.assertEqual(url, '/authentication/password-reset-request')
    
    def test_password_reset_request_url_validate_name(self):
        """Test the URL pattern for password reset request validate"""
        url = reverse('password-reset-validate', args=['uidb64', 'token'])
        self.assertEqual(url, '/authentication/password-reset-validate/uidb64/token')
    
    def test_password_reset_request_url_validate_resolves(self):
        """Test that the password reset validate URL resolves to the correct view"""
        url = reverse('password-reset-validate', args=['uidb64', 'token'])
        self.assertEqual(
            resolve(url).func.view_class,
            PasswordResetLinkValidateView
        )