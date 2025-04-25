from django.test import TestCase
from django.contrib.auth.hashers import make_password
from unittest.mock import MagicMock
from authentication.services import AuthService
from pt_backend.models import User

class AuthServiceTests(TestCase):
    def setUp(self):
        # Create mock repository
        self.mock_repository = MagicMock()
        self.auth_service = AuthService(self.mock_repository)
        
        # Create a test user object
        self.test_user = User(
            id=1,
            name='Test User',
            email='test@example.com',
            password=make_password('Password123!'), # NOSONAR – test data, not a real secret
            role='TENAGA_AHLI'
        )

    def test_login_success(self):
        """Test successful login - happy path"""
        # Configure mock
        self.mock_repository.get_user_by_email.return_value = self.test_user
        
        # Call the service
        result = self.auth_service.login('test@example.com', 'Password123!')
        
        # Verify
        self.assertIsNotNone(result)
        self.assertIn('access_token', result)
        self.mock_repository.get_user_by_email.assert_called_once_with('test@example.com')

    def test_login_invalid_email(self):
        """Test login with invalid email - unhappy path"""
        # Configure mock
        self.mock_repository.get_user_by_email.return_value = None
        
        # Call the service
        result = self.auth_service.login('wrong@example.com', 'Password123!')
        
        # Verify
        self.assertIsNone(result)
        self.mock_repository.get_user_by_email.assert_called_once_with('wrong@example.com')

    def test_login_invalid_password(self):
        """Test login with invalid password - unhappy path"""
        # Configure mock
        self.mock_repository.get_user_by_email.return_value = self.test_user
        
        # Call the service
        result = self.auth_service.login('test@example.com', 'WrongPassword123!')
        
        # Verify
        self.assertIsNone(result)
        self.mock_repository.get_user_by_email.assert_called_once_with('test@example.com')

    def test_login_empty_credentials(self):
        """Test login with empty credentials - edge case"""
        # Call with empty email
        result1 = self.auth_service.login('', 'Password123!')
        self.assertIsNone(result1)
        self.mock_repository.get_user_by_email.assert_called_with('')

        # Call with empty password
        self.mock_repository.get_user_by_email.reset_mock()
        self.mock_repository.get_user_by_email.return_value = self.test_user
        result2 = self.auth_service.login('test@example.com', '')
        
        self.assertIsNone(result2)
        self.mock_repository.get_user_by_email.assert_called_with('test@example.com')