from django.test import TestCase, override_settings
from django.contrib.auth.hashers import make_password
from unittest.mock import MagicMock
from django.utils import timezone
from authentication.services import AuthService
from pt_backend.models import User
from django.core.cache import cache

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

    def tearDown(self):
        # Clear cache between tests
        cache.clear()

    @override_settings(ACCOUNT_LOCKOUT={'MAX_FAILED_ATTEMPTS': 3, 'LOCKOUT_DURATION': 5})
    def test_increment_failed_attempts(self):
        """Test that failed login attempts are tracked correctly"""
        email = 'test@example.com'
        
        # Configure mock for failed login attempts
        self.mock_repository.get_user_by_email.return_value = self.test_user
        
        # Make 2 failed attempts (below threshold)
        self.auth_service.login(email, 'wrong1')
        self.auth_service.login(email, 'wrong2')
        
        # Check cache state after failed attempts
        cache_key = self.auth_service._get_lockout_cache_key(email)
        cached_data = cache.get(cache_key)
        
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data.get('attempts'), 2)
        self.assertNotIn('locked_until', cached_data)
    
    @override_settings(ACCOUNT_LOCKOUT={'MAX_FAILED_ATTEMPTS': 3, 'LOCKOUT_DURATION': 5})
    def test_account_lockout_after_max_attempts(self):
        """Test that account gets locked after max failed attempts"""
        email = 'test@example.com'
        
        # Configure mock
        self.mock_repository.get_user_by_email.return_value = self.test_user
        
        # Make enough failed login attempts to trigger lockout
        self.auth_service.login(email, 'wrong1')
        self.auth_service.login(email, 'wrong2')
        self.auth_service.login(email, 'wrong3')  # This should trigger the lockout
        
        # Try to login again with correct password
        result = self.auth_service.login(email, 'Password123!')
        
        # Verify account is locked
        self.assertIsNotNone(result)
        self.assertTrue(result.get('locked'))
        self.assertIn('message', result)
        self.assertIn('locked', result['message'])
    
    @override_settings(ACCOUNT_LOCKOUT={'MAX_FAILED_ATTEMPTS': 3, 'LOCKOUT_DURATION': 5})
    def test_account_unlocks_after_timeout(self):
        """Test that account unlocks after lockout period"""
        email = 'test@example.com'
        
        # Configure mock
        self.mock_repository.get_user_by_email.return_value = self.test_user
        
        # Make enough failed login attempts to trigger lockout
        self.auth_service.login(email, 'wrong1')
        self.auth_service.login(email, 'wrong2')
        self.auth_service.login(email, 'wrong3')
        
        # Verify account is locked
        result1 = self.auth_service.login(email, 'Password123!')
        self.assertTrue(result1.get('locked'))
        
        # Manipulate the cached data to simulate time passing
        cache_key = self.auth_service._get_lockout_cache_key(email)
        cached_data = cache.get(cache_key)
        cached_data['locked_until'] = timezone.now().timestamp() - 1  # Set to past time
        cache.set(cache_key, cached_data)
        
        # Try login again - should work now
        result2 = self.auth_service.login(email, 'Password123!')
        
        # Verify account is unlocked
        self.assertIsNotNone(result2)
        self.assertNotIn('locked', result2)
        self.assertIn('access_token', result2)
    
    @override_settings(ACCOUNT_LOCKOUT={'MAX_FAILED_ATTEMPTS': 3, 'LOCKOUT_DURATION': 5})
    def test_successful_login_resets_attempts(self):
        """Test that successful login resets the failed attempts counter"""
        email = 'test@example.com'
        
        # Configure mock
        self.mock_repository.get_user_by_email.return_value = self.test_user
        
        # Make some failed attempts (below threshold)
        self.auth_service.login(email, 'wrong1')
        self.auth_service.login(email, 'wrong2')
        
        # Check that attempts are being tracked
        cache_key = self.auth_service._get_lockout_cache_key(email)
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data.get('attempts'), 2)
        
        # Now login successfully
        self.auth_service.login(email, 'Password123!')
        
        # Check that attempts have been reset
        cached_data_after = cache.get(cache_key)
        self.assertIsNone(cached_data_after)
    
    @override_settings(ACCOUNT_LOCKOUT={'MAX_FAILED_ATTEMPTS': 3, 'LOCKOUT_DURATION': 5})
    def test_nonexistent_email_tracks_attempts(self):
        """Test that attempts with nonexistent emails are also tracked to prevent enumeration attacks"""
        email = 'nonexistent@example.com'
        
        # Configure mock for nonexistent email
        self.mock_repository.get_user_by_email.return_value = None
        
        # Make failed attempts with nonexistent email
        self.auth_service.login(email, 'anypassword1')
        self.auth_service.login(email, 'anypassword2')
        self.auth_service.login(email, 'anypassword3')
        
        # Check that attempts are tracked even for nonexistent emails
        cache_key = self.auth_service._get_lockout_cache_key(email)
        cached_data = cache.get(cache_key)
        
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data.get('attempts'), 3)