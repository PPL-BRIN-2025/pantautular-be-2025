from django.test import TestCase
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from unittest.mock import patch, MagicMock
from authentication.services import PasswordResetService
from django.contrib.auth.tokens import default_token_generator
from pt_backend.models import User

class TestPasswordResetService(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            email='test@example.com',
            name='testuser',
            password='oldpassword123',
            role="TEST ROLE"
        )
        self.service = PasswordResetService()
        
    def test_find_user_by_email_successful(self):
        """Test that a user can be found by email"""
        user = self.service.find_user_by_email('test@example.com')
        self.assertEqual(user.name, 'testuser')
        
    def test_generate_token_successful(self):
        """Test that token generation produces valid uid and token"""
        uid, token = self.service.generate_password_reset_token(self.user)
        # Verify uid decodes to the user's id
        decoded_uid = urlsafe_base64_decode(uid).decode()
        self.assertEqual(int(decoded_uid), self.user.id)
        # Token should be a non-empty string
        self.assertTrue(token and isinstance(token, str))
        
    def test_create_reset_link_successful(self):
        """Test that reset link creation works properly"""
        uid, token = self.service.generate_password_reset_token(self.user)
        link = self.service.create_password_reset_link(uid, token)
        self.assertTrue(link.startswith("http://localhost:3000/forgot-password/reset"))
        self.assertTrue(uid in link)
        self.assertTrue(token in link)
        
    @patch('authentication.services.send_mail')
    def test_send_reset_email_successful(self, mock_send_mail):
        """Test that email sending works properly"""
        self.service.send_password_reset_email('test@example.com', 'https://test.link')
        mock_send_mail.assert_called_once()
        
    @patch('authentication.services.PasswordResetService.send_password_reset_email')
    def test_process_reset_request_successful(self, mock_send_email):
        """Test the complete reset request flow"""
        result = self.service.process_reset_request('test@example.com')
        self.assertTrue(result)
        mock_send_email.assert_called_once()
    
    def test_find_nonexistent_user(self):
        """Test finding a user that doesn't exist"""
        user = self.service.find_user_by_email('nonexistent@example.com')
        self.assertIsNone(user)
        
    @patch('authentication.services.PasswordResetService.send_password_reset_email')
    def test_process_reset_nonexistent_user(self, mock_send_email):
        """Test processing reset with non-existent user"""
        with self.assertRaises(AttributeError):  # Since user will be None
            self.service.process_reset_request('nonexistent@example.com')
        
    @patch('authentication.services.send_mail')
    def test_send_email_error(self, mock_send_mail):
        """Test handling email sending error"""
        mock_send_mail.side_effect = Exception("Email error")
        with self.assertRaises(Exception):
            self.service.send_password_reset_email('test@example.com', 'https://test.link')
            
    def test_generate_token_invalid_user(self):
        """Test token generation with invalid user"""
        invalid_user = MagicMock()
        invalid_user.pk = None
        with self.assertRaises(Exception):
            self.service.generate_password_reset_token(invalid_user)
    
    def test_empty_email(self):
        """Test handling empty email"""
        user = self.service.find_user_by_email('')
        self.assertIsNone(user)
        
    @patch('authentication.services.send_mail')
    def test_unicode_email(self, mock_send_mail):
        """Test handling email with unicode characters"""
        User.objects.create(
            email='tëst@exämple.com',
            name='unicodeuser',
            password='password123',
            role="TEST ROLE"
        )
        
        self.service.send_password_reset_email('tëst@exämple.com', 'https://test.link')
        mock_send_mail.assert_called_once()
        
    def test_special_chars_in_url(self):
        """Test handling special characters in URL base"""
        service = PasswordResetService(reset_url_base="http://localhost:3000/authentication/reset-password?special=!@#$%^&*()")
        uid, token = service.generate_password_reset_token(self.user)
        link = service.create_password_reset_link(uid, token)
        self.assertTrue('!@#$%^&*()' in link)
    
    def test_get_user_from_uidb64_valid(self):
        """Test retrieving a user from a valid uidb64"""
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        user = self.service.get_user_from_uidb64(uidb64)
        self.assertEqual(user.id, self.user.id)
        self.assertEqual(user.email, 'test@example.com')

    def test_get_user_from_uidb64_invalid_format(self):
        """Test retrieving a user with invalid uidb64 format"""
        user = self.service.get_user_from_uidb64('invalid-base64')
        self.assertIsNone(user)

    def test_get_user_from_uidb64_nonexistent_user(self):
        """Test retrieving a non-existent user from uidb64"""
        uidb64 = urlsafe_base64_encode(force_bytes(99999))
        user = self.service.get_user_from_uidb64(uidb64)
        self.assertIsNone(user)

    def test_get_user_from_uidb64_empty(self):
        """Test retrieving a user with empty uidb64"""
        user = self.service.get_user_from_uidb64('')
        self.assertIsNone(user)

    def test_validate_token_valid(self):
        """Test validating a valid token"""
        token = default_token_generator.make_token(self.user)
        result = self.service.validate_token(self.user, token)
        self.assertTrue(result)

    def test_validate_token_invalid(self):
        """Test validating an invalid token"""
        token = "invalid-token"
        result = self.service.validate_token(self.user, token)
        self.assertFalse(result)

    def test_validate_token_none_user(self):
        """Test validating a token with None user"""
        token = "some-token"
        result = self.service.validate_token(None, token)
        self.assertFalse(result)

    def test_validate_token_empty(self):
        """Test validating an empty token"""
        token = ""
        result = self.service.validate_token(self.user, token)
        self.assertFalse(result)