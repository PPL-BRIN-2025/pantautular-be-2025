from django.test import TestCase
from pt_backend.models import User
from django.contrib.auth.hashers import make_password
from authentication.repository import UserRepository

class UserRepositoryTest(TestCase):
    
    def setUp(self):
        self.user = User.objects.create(
            name="Test User",
            email="test@example.com",
            password=make_password("correct_password"), # NOSONAR - test data only
            role="USER"
        )
        self.repository = UserRepository()
    
    def test_verify_password_correct(self):
        """Test verify_password with correct password"""
        result = self.repository.verify_password(self.user, "correct_password")
        self.assertTrue(result)
    
    def test_verify_password_incorrect(self):
        """Test verify_password with incorrect password"""
        result = self.repository.verify_password(self.user, "wrong_password")
        self.assertFalse(result)
    
    def test_verify_password_empty(self):
        """Test verify_password with empty password"""
        result = self.repository.verify_password(self.user, "")
        self.assertFalse(result)
        
    def test_verify_password_none(self):
        """Test verify_password with None password"""
        result = self.repository.verify_password(self.user, None)
        self.assertFalse(result)