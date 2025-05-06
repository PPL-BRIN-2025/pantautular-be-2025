from django.test import TestCase
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from unittest.mock import MagicMock, patch
from authentication.services import (
    PasswordResetService, PasswordValidationService,
    UserFinderService, PasswordTokenService)
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.hashers import check_password
from pt_backend.models import User
from authentication.tests.forgot_password.mock_email_service import MockEmailService
from authentication.email_services import BrevoEmailService, DjangoEmailService
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
        
        self.assertTrue(link.startswith("https"))
        
        expected_format = f"{self.service.reset_url_base}/{uid}/{token}"
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
    
    def test_password_reset_service_default_email_service(self):
        """Test that PasswordResetService uses default email service when none provided"""
        with patch('authentication.email_services.BrevoEmailService.send_password_reset_email') as mock_send:
            service = PasswordResetService() 
            
            service.process_reset_request('test@example.com')
            
            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            self.assertEqual(args[0], 'test@example.com')


    def test_email_service_error_handling(self):
        """Test error handling in different email services"""
        
        with patch('authentication.email_services.TransactionalEmailsApi') as mock_api:
            mock_instance = MagicMock()
            mock_api.return_value = mock_instance
            mock_instance.send_transac_email.side_effect = ApiException(reason="API Error")
            
            brevo_service = BrevoEmailService()
            
            with self.assertRaises(ApiException):
                brevo_service.send_password_reset_email("test@example.com", "https://reset.link")
    

    def test_email_chain_handles_multiple_failures(self):
        """Test that chain properly handles multiple failures"""
        # Create multiple mock handlers that will fail
        first_handler = MockEmailService(should_fail=True) 
        second_handler = MockEmailService(should_fail=True)
        third_handler = MockEmailService()  # This one will succeed
        
        # Build the chain
        first_handler.set_next(second_handler)
        second_handler.set_next(third_handler)
        
        # Create service with this chain
        service = PasswordResetService(email_chain=first_handler)
        
        # Process request
        service.process_reset_request('test@example.com')
        
        # First two handlers should have failed, third should have sent
        self.assertEqual(len(third_handler.sent_emails), 1)
        self.assertEqual(third_handler.sent_emails[0]["recipient"], 'test@example.com')

    def test_email_chain_initialization(self):
        """Test that email chain is initialized correctly with default services"""
        service = PasswordResetService()
        
        # First handler should be BrevoEmailService
        self.assertIsInstance(service.email_chain, BrevoEmailService)
        
        # Next handler should be DjangoEmailService
        self.assertIsInstance(service.email_chain._next_handler, DjangoEmailService)
        
        # End of chain
        # self.assertIsNone(service.email_chain._next_handler._next_handler)

    def test_custom_email_chain(self):
        """Test that a custom email chain can be provided"""
        # Create a custom chain
        first = MockEmailService()
        second = MockEmailService()
        first.set_next(second)
        
        # Initialize with custom chain
        service = PasswordResetService(email_chain=first)
        
        # Chain should be used
        self.assertEqual(service.email_chain, first)
        self.assertEqual(service.email_chain._next_handler, second)

    @patch('authentication.email_services.BrevoEmailService.send_password_reset_email')
    def test_first_email_service_succeeds(self, mock_send):
        """Test when first service in chain succeeds"""
        # Setup
        mock_send.return_value = True
        
        # Call method
        self.service.process_reset_request('test@example.com')
        
        # Only first service should be called
        mock_send.assert_called_once()

    @patch('authentication.email_services.BrevoEmailService.send_password_reset_email')
    @patch('authentication.email_services.DjangoEmailService.send_password_reset_email')
    def test_chain_fallback_on_failure(self, mock_django_send, mock_brevo_send):
        """Test chain fallback when first service fails"""
        # First service fails
        mock_brevo_send.side_effect = Exception("Brevo API error")
        
        # Second service succeeds
        mock_django_send.return_value = True
        
        # Call method
        self.service.process_reset_request('test@example.com')
        
        # Both services should be called in order
        mock_brevo_send.assert_called_once()
        mock_django_send.assert_called_once()

    @patch('authentication.email_services.BrevoEmailService.handle')
    def test_handle_method_is_called(self, mock_handle):
        """Test that handle method is called on the chain"""
        # Setup
        mock_handle.return_value = True
        
        # Process reset request 
        self.service.process_reset_request('test@example.com')
        
        # Handle should be called with correct parameters
        mock_handle.assert_called_once()
        args = mock_handle.call_args[0]
        self.assertEqual(args[0], 'test@example.com')
        # Second arg should be the reset link
        self.assertTrue(isinstance(args[1], str) and args[1].startswith('https'))

    def test_process_reset_nonexistent_email(self):
        """Test process_reset_request with non-existent email"""
        # Create a mock email chain
        mock_chain = MockEmailService()
        service = PasswordResetService(email_chain=mock_chain)
        
        # Call with non-existent email
        service.process_reset_request('nonexistent@example.com')
        
        # Chain should not be called since user is None
        self.assertEqual(len(mock_chain.sent_emails), 0)

    def test_get_user_from_uidb64_with_none_value(self):
        """Test get_user_from_uidb64 when uidb64 is None"""
        user = self.service.get_user_from_uidb64(None)
        self.assertIsNone(user)

class TestUserFinderService(TestCase):
    def setUp(self):
        # Create a mock repository
        self.repository = MagicMock()
        # Create the service with the mock repository
        self.service = UserFinderService(self.repository)
        
    def test_find_user_by_email_successful(self):
        """Test finding a user by email successfully"""
        # Setup mock to return a user when get_user_by_email is called
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        self.repository.get_user_by_email.return_value = mock_user
        
        # Call the service
        result = self.service.find_user_by_email("test@example.com")
        
        # Verify repository was called with correct parameters
        self.repository.get_user_by_email.assert_called_once_with("test@example.com")
        
        # Verify the result
        self.assertEqual(result.email, "test@example.com")
        self.assertEqual(result.name, "Test User")
        
    def test_find_user_by_email_not_found(self):
        """Test finding a user by email when user doesn't exist"""
        # Setup mock to return None when get_user_by_email is called
        self.repository.get_user_by_email.return_value = None
        
        # Call the service
        result = self.service.find_user_by_email("nonexistent@example.com")
        
        # Verify repository was called with correct parameters
        self.repository.get_user_by_email.assert_called_once_with("nonexistent@example.com")
        
        # Verify the result is None
        self.assertIsNone(result)
        
    def test_find_user_by_id_successful(self):
        """Test finding a user by ID successfully"""
        # Setup mock to return a user when get_user_by_id is called
        mock_user = MagicMock()
        mock_user.id = 123
        mock_user.name = "Test User"
        self.repository.get_user_by_id.return_value = mock_user
        
        # Call the service
        result = self.service.find_user_by_id(123)
        
        # Verify repository was called with correct parameters
        self.repository.get_user_by_id.assert_called_once_with(123)
        
        # Verify the result
        self.assertEqual(result.id, 123)
        self.assertEqual(result.name, "Test User")
        
    def test_find_user_by_id_not_found(self):
        """Test finding a user by ID when user doesn't exist"""
        # Setup mock to return None when get_user_by_id is called
        self.repository.get_user_by_id.return_value = None
        
        # Call the service
        result = self.service.find_user_by_id(999)
        
        # Verify repository was called with correct parameters
        self.repository.get_user_by_id.assert_called_once_with(999)
        
        # Verify the result is None
        self.assertIsNone(result)
        
    def test_find_user_by_email_with_empty_email(self):
        """Test finding a user with an empty email string"""
        # Call the service with empty email
        self.service.find_user_by_email("")
        
        # Verify repository was called with empty string
        self.repository.get_user_by_email.assert_called_once_with("")
        
    def test_find_user_by_email_handles_special_characters(self):
        """Test finding a user with special characters in email"""
        # Call the service with email containing special characters
        self.service.find_user_by_email("test+special@example.com")
        
        # Verify repository was called with the special email
        self.repository.get_user_by_email.assert_called_once_with("test+special@example.com")
        
    def test_find_user_by_id_with_invalid_id(self):
        """Test finding a user with an invalid ID type"""
        # Call the service with a string ID instead of an integer
        self.service.find_user_by_id("not-an-id")
        
        # Verify repository was called with the string
        self.repository.get_user_by_id.assert_called_once_with("not-an-id")
        
    def test_repository_exception_handling(self):
        """Test that service properly passes through repository exceptions"""
        # Setup repository to raise an exception
        self.repository.get_user_by_email.side_effect = Exception("Database error")
        
        # Verify exception is propagated
        with self.assertRaises(Exception) as context:
            self.service.find_user_by_email("test@example.com")
            
        self.assertEqual(str(context.exception), "Database error")

class TestPasswordTokenService(TestCase):
    def setUp(self):
        """Set up test environment for PasswordTokenService"""
        # Create a test user
        self.user = User.objects.create(
            email='tokentest@example.com',
            name='Token Test User',
            password='password123',
            role="TEST ROLE"
        )
        
        # Create a mock repository
        self.repository = MagicMock()
        self.repository.get_user_by_id.return_value = self.user
        
        # Initialize the service with mock repository
        self.service = PasswordTokenService(self.repository)
    
    def test_generate_token_creates_valid_pair(self):
        """Test that token generation produces a valid UID and token pair"""
        uid, token = self.service.generate_password_reset_token(self.user)
        
        # Verify uid is correctly encoded
        decoded_uid = urlsafe_base64_decode(uid).decode()
        self.assertEqual(int(decoded_uid), self.user.id)
        
        # Verify token is a non-empty string
        self.assertTrue(token and isinstance(token, str))
        
        # Verify token is valid for the user
        self.assertTrue(default_token_generator.check_token(self.user, token))
    
    def test_generate_token_with_none_user(self):
        """Test token generation with None user"""
        with self.assertRaises(AttributeError):
            self.service.generate_password_reset_token(None)
    
    def test_get_user_from_valid_uidb64(self):
        """Test retrieving a user from a valid uidb64"""
        # Generate a valid uidb64
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        
        # Get user from uidb64
        user = self.service.get_user_from_uidb64(uidb64)
        
        # Verify repository was called correctly
        self.repository.get_user_by_id.assert_called_once_with(str(self.user.pk))
        
        # Verify correct user was returned
        self.assertEqual(user, self.user)
    
    def test_get_user_from_invalid_uidb64(self):
        """Test retrieving a user with invalid uidb64 format"""
        # Setup repository to return None for invalid ID
        self.repository.get_user_by_id.return_value = None
        
        # Test with invalid base64
        user = self.service.get_user_from_uidb64('invalid-base64!')
        
        # Verify no user was returned
        self.assertIsNone(user)
        
        # Verify repository was not called with invalid data
        self.repository.get_user_by_id.assert_not_called()
    
    def test_get_user_from_nonexistent_user_id(self):
        """Test retrieving a non-existent user from uidb64"""
        # Setup repository to return None for non-existent ID
        self.repository.get_user_by_id.return_value = None
        
        # Generate uidb64 for a non-existent user ID
        uidb64 = urlsafe_base64_encode(force_bytes(99999))
        
        # Get user from uidb64
        user = self.service.get_user_from_uidb64(uidb64)
        
        # Verify repository was called with correct ID
        self.repository.get_user_by_id.assert_called_once_with("99999")
        
        # Verify no user was returned
        self.assertIsNone(user)
    
    def test_get_user_from_none_uidb64(self):
        """Test retrieving a user with None uidb64"""
        user = self.service.get_user_from_uidb64(None)
        
        # Verify no user was returned
        self.assertIsNone(user)
        
        # Verify repository was not called
        self.repository.get_user_by_id.assert_not_called()
    
    def test_validate_valid_token(self):
        """Test validating a valid token"""
        # Generate a valid token
        token = default_token_generator.make_token(self.user)
        
        # Validate token
        result = self.service.validate_token(self.user, token)
        
        # Verify token was validated successfully
        self.assertTrue(result)
    
    def test_validate_invalid_token(self):
        """Test validating an invalid token"""
        # Test with an invalid token
        result = self.service.validate_token(self.user, "invalid-token")
        
        # Verify token validation failed
        self.assertFalse(result)
    
    def test_validate_token_with_none_user(self):
        """Test validating a token with None user"""
        result = self.service.validate_token(None, "any-token")
        
        # Verify validation fails with None user
        self.assertFalse(result)
    
    def test_validate_empty_token(self):
        """Test validating an empty token"""
        result = self.service.validate_token(self.user, "")
        
        # Verify validation fails with empty token
        self.assertFalse(result)
    
    def test_repository_exception_handling(self):
        """Test exception handling when repository fails"""
        # Setup repository to raise an exception
        self.repository.get_user_by_id.side_effect = User.DoesNotExist("User not found")
        
        # Generate valid uidb64
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        
        # Get user from uidb64 should catch the exception
        user = self.service.get_user_from_uidb64(uidb64)
        
        # Verify no user was returned
        self.assertIsNone(user)
        
        # Verify repository was called
        self.repository.get_user_by_id.assert_called_once()

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
        password = "UPPERCASE123!" # NOSONAR – test data, not a real secret
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