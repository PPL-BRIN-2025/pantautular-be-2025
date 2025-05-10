from django.test import TestCase
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from unittest.mock import MagicMock, patch
from authentication.email_services import PasswordResetEmailStrategy
from authentication.services import (
    PasswordResetService, PasswordValidationService,
    UserFinderService, PasswordTokenService, ResetLinkService)
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.hashers import check_password
from pt_backend.models import User

class TestPasswordResetService(TestCase):
    def setUp(self):
        """Set up test environment for PasswordResetService"""
        # Create mocks for dependencies
        self.user_finder = MagicMock()
        self.password_token_service = MagicMock()
        self.reset_link_service = MagicMock()
        self.email_service = MagicMock()
        
        # Create a test user
        self.user = MagicMock()
        self.user.email = "test@example.com"
        self.user.pk = 123
        
        # Create the service with mock dependencies
        self.service = PasswordResetService(
            user_finder=self.user_finder,
            password_token_service=self.password_token_service,
            reset_link_service=self.reset_link_service,
            email_service=self.email_service
        )
        
        # Set up common mock returns
        self.user_finder.find_user_by_email.return_value = self.user
        self.password_token_service.generate_password_reset_token.return_value = ("test-uid", "test-token")
        self.reset_link_service.create_password_reset_link.return_value = "https://example.com/reset/test-uid/test-token"
    
    def test_initiate_password_reset_successful(self):
        """Test successful password reset email sending"""
        # Call the service
        result = self.service.initiate_password_reset("test@example.com")
        
        # Verify dependencies were called with correct parameters
        self.user_finder.find_user_by_email.assert_called_once_with("test@example.com")
        self.password_token_service.generate_password_reset_token.assert_called_once_with(self.user)
        self.reset_link_service.create_password_reset_link.assert_called_once_with("test-uid", "test-token")
        
        # Verify email service was called with strategy pattern
        self.email_service.send_email.assert_called_once()
        call_kwargs = self.email_service.send_email.call_args.kwargs
        self.assertEqual(call_kwargs["recipient_email"], "test@example.com")
        self.assertEqual(call_kwargs["reset_link"], "https://example.com/reset/test-uid/test-token")
        self.assertIsInstance(call_kwargs["strategy"], PasswordResetEmailStrategy)
        
        # Verify success result
        self.assertTrue(result)
    
    def test_initiate_password_reset_nonexistent_email(self):
        """Test handling non-existent email"""
        # Setup mock to return None for the email
        self.user_finder.find_user_by_email.return_value = None
        
        # Call the service
        result = self.service.initiate_password_reset("nonexistent@example.com")
        
        # Verify only user finder was called
        self.user_finder.find_user_by_email.assert_called_once_with("nonexistent@example.com")
        self.password_token_service.generate_password_reset_token.assert_not_called()
        self.reset_link_service.create_password_reset_link.assert_not_called()
        self.email_service.send_email.assert_not_called()
        
        # Verify true is returned (for security reasons)
        self.assertTrue(result)
    
    def test_initiate_password_reset_link_creation_fails(self):
        """Test handling when reset link creation fails"""
        # Setup mock to return None for link creation
        self.reset_link_service.create_password_reset_link.return_value = None
        
        # Call the service
        result = self.service.initiate_password_reset("test@example.com")
        
        # Verify all dependencies except email service were called
        self.user_finder.find_user_by_email.assert_called_once_with("test@example.com")
        self.password_token_service.generate_password_reset_token.assert_called_once_with(self.user)
        self.reset_link_service.create_password_reset_link.assert_called_once_with("test-uid", "test-token")
        self.email_service.send_email.assert_not_called()
        
        # Verify false is returned
        self.assertFalse(result)
    
    def test_initiate_password_reset_email_service_runtime_error(self):
        """Test handling when email service throws RuntimeError"""
        # Setup mock to raise RuntimeError
        self.email_service.send_email.side_effect = RuntimeError("Email service failed")
        
        # Call the service
        result = self.service.initiate_password_reset("test@example.com")
        
        # Verify all dependencies were called
        self.user_finder.find_user_by_email.assert_called_once_with("test@example.com")
        self.password_token_service.generate_password_reset_token.assert_called_once_with(self.user)
        self.reset_link_service.create_password_reset_link.assert_called_once_with("test-uid", "test-token")
        self.email_service.send_email.assert_called_once()
        
        # Verify false is returned
        self.assertFalse(result)
    
    def test_initiate_password_reset_email_service_generic_exception(self):
        """Test handling when email service throws a generic exception"""
        # Setup mock to raise Exception
        self.email_service.send_email.side_effect = Exception("Unexpected error")
        
        # Call the service
        result = self.service.initiate_password_reset("test@example.com")
        
        # Verify all dependencies were called
        self.user_finder.find_user_by_email.assert_called_once_with("test@example.com")
        self.password_token_service.generate_password_reset_token.assert_called_once_with(self.user)
        self.reset_link_service.create_password_reset_link.assert_called_once_with("test-uid", "test-token")
        self.email_service.send_email.assert_called_once()
        
        # Verify false is returned
        self.assertFalse(result)
    
    def test_initiate_password_reset_token_generation_exception(self):
        """Test handling when token generation fails"""
        # Setup mock to raise Exception
        self.password_token_service.generate_password_reset_token.side_effect = Exception("Token generation failed")
        
        # Call the service
        result = self.service.initiate_password_reset("test@example.com")
        
        # Verify only user finder and token generation were called
        self.user_finder.find_user_by_email.assert_called_once_with("test@example.com")
        self.password_token_service.generate_password_reset_token.assert_called_once_with(self.user)
        self.reset_link_service.create_password_reset_link.assert_not_called()
        self.email_service.send_email.assert_not_called()
        
        # Verify false is returned
        self.assertFalse(result)
    
    def test_verify_reset_attempt_successful(self):
        """Test successful reset attempt verification"""
        # Setup mocks
        self.password_token_service.get_user_from_uidb64.return_value = self.user
        self.password_token_service.validate_token.return_value = True
        
        # Call the service
        result = self.service.verify_reset_attempt("test-uid", "test-token")
        
        # Verify dependencies were called with correct parameters
        self.password_token_service.get_user_from_uidb64.assert_called_once_with("test-uid")
        self.password_token_service.validate_token.assert_called_once_with(self.user, "test-token")
        
        # Verify user was returned
        self.assertEqual(result, self.user)
    
    def test_verify_reset_attempt_invalid_uid(self):
        """Test verification with invalid UID"""
        # Setup mock to return None for UID
        self.password_token_service.get_user_from_uidb64.return_value = None
        
        # Call the service
        result = self.service.verify_reset_attempt("invalid-uid", "test-token")
        
        # Verify only get_user_from_uidb64 was called
        self.password_token_service.get_user_from_uidb64.assert_called_once_with("invalid-uid")
        self.password_token_service.validate_token.assert_not_called()
        
        # Verify None was returned
        self.assertIsNone(result)
    
    def test_verify_reset_attempt_invalid_token(self):
        """Test verification with invalid token"""
        # Setup mocks
        self.password_token_service.get_user_from_uidb64.return_value = self.user
        self.password_token_service.validate_token.return_value = False
        
        # Call the service
        result = self.service.verify_reset_attempt("test-uid", "invalid-token")
        
        # Verify both dependencies were called
        self.password_token_service.get_user_from_uidb64.assert_called_once_with("test-uid")
        self.password_token_service.validate_token.assert_called_once_with(self.user, "invalid-token")
        
        # Verify None was returned
        self.assertIsNone(result)

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

class TestResetLinkService(TestCase):
    def setUp(self):
        """Set up test environment for ResetLinkService"""
        # Create a default service with a test URL base
        self.default_url_base = "http://example.com/reset-password"
        self.service = ResetLinkService(reset_url_base=self.default_url_base)
        
    def test_init_with_explicit_url(self):
        """Test initialization with explicitly provided URL base"""
        custom_url = "https://custom.example.com/reset"
        service = ResetLinkService(reset_url_base=custom_url)
        self.assertEqual(service.reset_url_base, custom_url)
        
    @patch('os.getenv')
    def test_init_with_prod_env_url(self, mock_getenv):
        """Test initialization using production URL from environment"""
        # Setup mock to return prod URL for first call, dev URL for second call
        mock_getenv.side_effect = ["https://prod.example.com/reset", "https://dev.example.com/reset"]
        
        service = ResetLinkService()
        
        # Should use prod URL since it's available
        self.assertEqual(service.reset_url_base, "https://prod.example.com/reset")
        
    @patch('os.getenv')
    def test_init_with_dev_env_url(self, mock_getenv):
        """Test initialization using development URL from environment when prod is not available"""
        # Setup mock to return None for prod URL, dev URL for second call
        mock_getenv.side_effect = [None, "https://dev.example.com/reset"]
        
        service = ResetLinkService()
        
        # Should use dev URL since prod is not available
        self.assertEqual(service.reset_url_base, "https://dev.example.com/reset")
        
    @patch('authentication.services.os.getenv')
    @patch('builtins.print')
    def test_init_with_no_url_available(self, mock_print, mock_getenv):
        """Test initialization when no URL is available in env vars or parameters"""
        # Setup mock to return None for both URLs
        mock_getenv.return_value = None
        
        service = ResetLinkService()
        
        # URL base should be None
        self.assertIsNone(service.reset_url_base)
        
    def test_create_reset_link_successful(self):
        """Test successful creation of a reset link"""
        uid = "test-uid"
        token = "test-token"
        
        link = self.service.create_password_reset_link(uid, token)
        
        # Verify the link format
        expected_link = f"{self.default_url_base}/{uid}/{token}"
        self.assertEqual(link, expected_link)
        
    @patch('builtins.print')
    @patch('authentication.services.os.getenv')
    def test_create_reset_link_with_no_base_url(self, mock_getenv, mock_print ):
        """Test link creation when base URL is not set"""
        mock_getenv.return_value = None

        # Create service with no base URL
        service = ResetLinkService(reset_url_base=None)
        link = service.create_password_reset_link("uid", "token")
        self.assertIsNone(link)

    def test_create_reset_link_with_special_characters(self):
        """Test link creation with special characters in parameters"""
        uid = "test+uid@special"
        token = "test&token=special"
        
        link = self.service.create_password_reset_link(uid, token)
        
        # Verify special characters are preserved correctly
        expected_link = f"{self.default_url_base}/{uid}/{token}"
        self.assertEqual(link, expected_link)
        self.assertTrue("test+uid@special" in link)
        self.assertTrue("test&token=special" in link)
        
    def test_create_reset_link_with_unicode_characters(self):
        """Test link creation with unicode characters"""
        uid = "测试uid"
        token = "测试token"
        
        link = self.service.create_password_reset_link(uid, token)
        
        # Verify unicode characters are preserved
        expected_link = f"{self.default_url_base}/{uid}/{token}"
        self.assertEqual(link, expected_link)
        
    def test_url_with_query_parameters(self):
        """Test using a base URL that already contains query parameters"""
        # Create service with a URL that has query parameters
        url_with_params = "http://example.com/reset?param=value"
        service = ResetLinkService(reset_url_base=url_with_params)
        
        link = service.create_password_reset_link("uid", "token")
        
        # Verify the parameters were kept
        expected_link = f"{url_with_params}/uid/token"
        self.assertEqual(link, expected_link)
        self.assertTrue("param=value" in link)

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