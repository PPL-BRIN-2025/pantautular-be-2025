from django.test import TestCase
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from unittest.mock import MagicMock, patch
from authentication.services import PasswordResetService, ChangePasswordService, PasswordValidationService
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.hashers import check_password
from pt_backend.models import User
from authentication.tests.forgot_password.mock_email_service import MockEmailService
from authentication.email_services import BrevoEmailService
from sib_api_v3_sdk.rest import ApiException

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
        decoded_uid = urlsafe_base64_decode(uid).decode()
        self.assertEqual(int(decoded_uid), self.user.id)
        self.assertTrue(token and isinstance(token, str))
        
    def test_create_reset_link_successful(self):
        """Test that reset link creation works properly"""
        uid, token = self.service.generate_password_reset_token(self.user)
        link = self.service.create_password_reset_link(uid, token)
        
        self.assertTrue(link.startswith("http://localhost:3000/forgot-password/reset"))
        
        self.assertTrue(f"?uid={uid}" in link)
        self.assertTrue(f"&token={token}" in link)
        
        expected_format = f"{self.service.reset_url_base}?uid={uid}&token={token}"
        self.assertEqual(link, expected_format)
        
    def test_find_nonexistent_user(self):
        """Test finding a user that doesn't exist"""
        user = self.service.find_user_by_email('nonexistent@example.com')
        self.assertIsNone(user)
        
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

    def test_password_reset_service_with_mock_email(self):
        """Test PasswordResetService with a mock email service"""
        
        mock_email_service = MockEmailService()
        service = PasswordResetService(email_service=mock_email_service)
        
        service.process_reset_request('test@example.com')
        
        self.assertEqual(len(mock_email_service.sent_emails), 1)
        self.assertEqual(mock_email_service.sent_emails[0]["recipient"], 'test@example.com')
    
    def test_password_reset_service_default_email_service(self):
        """Test that PasswordResetService uses default email service when none provided"""
        with patch('authentication.email_services.BrevoEmailService.send_password_reset_email') as mock_send:
            service = PasswordResetService() 
            
            service.process_reset_request('test@example.com')
            
            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            self.assertEqual(args[0], 'test@example.com')
    
    def test_password_reset_service_with_brevo_email(self):
        """Test PasswordResetService with Brevo email service"""
        from authentication.email_services import BrevoEmailService
        with patch('authentication.email_services.TransactionalEmailsApi') as mock_api:
            mock_instance = MagicMock()
            mock_api.return_value = mock_instance
            
            email_service = BrevoEmailService()
            service = PasswordResetService(email_service=email_service)
            
            service.process_reset_request('test@example.com')
            
            mock_instance.send_transac_email.assert_called_once()

    def test_email_service_error_handling(self):
        """Test error handling in different email services"""
        
        with patch('authentication.email_services.TransactionalEmailsApi') as mock_api:
            mock_instance = MagicMock()
            mock_api.return_value = mock_instance
            mock_instance.send_transac_email.side_effect = ApiException(reason="API Error")
            
            brevo_service = BrevoEmailService()
            
            with self.assertRaises(ApiException):
                brevo_service.send_password_reset_email("test@example.com", "https://reset.link")

class ChangePasswordServiceTest(TestCase):

    def test_change_password_success(self):
        user = User.objects.create(name="Charlie", email="charlie@example.com", password="oldpass", role="USER") # NOSONAR – test data, not a real secret
        service = ChangePasswordService()
        result = service.change_password("charlie@example.com", "newsecurepass")

        user.refresh_from_db()
        self.assertTrue(result)
        self.assertTrue(check_password("newsecurepass", user.password)) # NOSONAR – test data, not a real secret

    def test_change_password_user_not_found(self):
        service = ChangePasswordService()
        result = service.change_password("ghost@example.com", "pass")
        self.assertFalse(result)

    def test_change_password_empty_password(self):
        user = User.objects.create(name="Dana", email="dana@example.com", password="oldpass", role="USER") # NOSONAR – test data, not a real secret
        service = ChangePasswordService()
        result = service.change_password("dana@example.com", "")

        user.refresh_from_db()
        self.assertTrue(result)
        self.assertTrue(check_password("", user.password)) # NOSONAR – test data, not a real secret

    def test_change_password_reuse_same_password(self):
        user = User.objects.create(name="Eli", email="eli@example.com", password="oldpass", role="USER") # NOSONAR – test data, not a real secret
        service = ChangePasswordService()
        result = service.change_password("eli@example.com", "oldpass")

        user.refresh_from_db()
        self.assertTrue(result)
        self.assertTrue(check_password("oldpass", user.password))  # NOSONAR – test data, not a real secret

class TestPasswordValidationService(TestCase):
    def setUp(self):
        self.service = PasswordValidationService()

    def test_validate_password_match_success(self):
        """Test that a password matches the expected format"""
        password = "ValidPassword123!" # NOSONAR – test data, not a real secret
        password2 = "ValidPassword123!" # NOSONAR – test data, not a real secret
        result = self.service.validate_password_match(password, password2)
        self.assertTrue(result)

    def test_validate_password_match_failure(self):
        """Test that a password does not match the expected format"""
        password = "ValidPassword123!" # NOSONAR – test data, not a real secret
        password2 = "DifferentPassword123!" # NOSONAR – test data, not a real secret
        result = self.service.validate_password_match(password, password2)
        self.assertFalse(result)

    def test_validate_password_success(self):
        """Test that a valid password passes validation"""
        password = "ValidPassword123!" # NOSONAR – test data, not a real secret
        result, detail = self.service.validate_password_strength(password)
        self.assertTrue(result)
        self.assertEqual(detail, "")

    def test_validate_password_too_short(self):
        """Test that a short password fails validation"""
        password = "short" # NOSONAR – test data, not a real secret
        result, detail = self.service.validate_password_strength(password)
        self.assertFalse(result)
        self.assertEqual(detail, "Password harus minimal 8 karakter")

    def test_validate_password_no_uppercase(self):
        """Test that a password without uppercase letters fails validation"""
        password = "lowercase123!" # NOSONAR – test data, not a real secret
        result, detail = self.service.validate_password_strength(password)
        self.assertFalse(result)
        self.assertEqual(detail, "Password harus mengandung minimal 1 huruf besar")

    def test_validate_password_no_lowercase(self):
        """Test that a password without lowercase letters fails validation"""
        password = "UPPERCASE123!"
        result, detail = self.service.validate_password_strength(password)
        self.assertFalse(result)
        self.assertEqual(detail, "Password harus mengandung minimal 1 huruf kecil")

    def test_validate_password_no_numbers(self):
        """Test that a password without numbers fails validation"""
        password = "NoNumbers!" # NOSONAR – test data, not a real secret
        result, detail = self.service.validate_password_strength(password)
        self.assertFalse(result)
        self.assertEqual(detail, "Password harus mengandung minimal 1 angka")

    def test_validate_password_no_special_characters(self):
        """Test that a password without special characters fails validation"""
        password = "NoSpecialChars123" # NOSONAR – test data, not a real secret
        result, detail = self.service.validate_password_strength(password)
        self.assertFalse(result)
        self.assertEqual(detail, "Password harus mengandung minimal 1 karakter spesial")

    def test_validate_password_empty(self):
        """Test that an empty password fails validation"""
        password = "" # NOSONAR – test data, not a real secret
        result, detail = self.service.validate_password_strength(password)
        self.assertFalse(result)
        self.assertEqual(detail, "Password harus minimal 8 karakter")