from django.test import TestCase
from django.contrib.auth.hashers import make_password
from authentication.repositories import UserRepository
from pt_backend.models import User

class UserRepositoryTests(TestCase):
    def setUp(self):
        # Create test users
        self.test_user = User.objects.create(
            name='Test User',
            email='test@example.com',
            password=make_password('Password123!'), # NOSONAR – test data, not a real secret
            role='TENAGA_AHLI'
        )
        self.repository = UserRepository()

    def test_get_user_by_email_success(self):
        """Test retrieving user by email - happy path"""
        user = self.repository.get_user_by_email('test@example.com')
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.name, 'Test User')

    def test_get_user_by_email_case_insensitive(self):
        """Test case insensitivity when retrieving by email - edge case"""
        user = self.repository.get_user_by_email('TEST@example.com')
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'test@example.com')

    def test_get_user_by_email_nonexistent(self):
        """Test retrieving non-existent user - unhappy path"""
        user = self.repository.get_user_by_email('nonexistent@example.com')
        self.assertIsNone(user)