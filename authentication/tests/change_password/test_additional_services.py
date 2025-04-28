from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from pt_backend.models import User
from django.contrib.auth.hashers import make_password
from authentication.services import ChangePasswordService
from unittest.mock import patch, Mock

class ChangePasswordServiceAdditionalTest(TestCase):
    
    def setUp(self):
        self.user = User.objects.create(
            name="Test User",
            email="test@example.com",
            password=make_password("current_password"), # NOSONAR - test data only
            role="USER"
        )
        self.service = ChangePasswordService()
        
    def test_get_user_from_uidb64_valid(self):
        """Test successfully retrieving user from uidb64"""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        
        retrieved_user = self.service.get_user_from_uidb64(uid)

        self.assertEqual(self.user.id, retrieved_user.id)
        self.assertEqual(self.user.email, retrieved_user.email)
        
    def test_get_user_from_uidb64_invalid(self):
        """Test retrieving user with invalid uidb64"""
        invalid_uids = [
            "invalid-uid",  # Not base64
            urlsafe_base64_encode(force_bytes("not-an-id")),  # Not numeric
            urlsafe_base64_encode(force_bytes(9999)),  # Non-existent ID
            None  # None value
        ]
        
        for uid in invalid_uids:
            user = self.service.get_user_from_uidb64(uid)
            self.assertIsNone(user, f"Expected None for invalid uid: {uid}")
    
    def test_validate_token_valid(self):
        """Test token validation with valid token"""
        token = default_token_generator.make_token(self.user)

        is_valid = self.service.validate_token(self.user, token)

        self.assertTrue(is_valid)
        
    def test_validate_token_invalid(self):
        """Test token validation with invalid token"""
        invalid_tokens = [
            "invalid-token",
            "1-abc",
            None
        ]
        
        for token in invalid_tokens:
            is_valid = self.service.validate_token(self.user, token)
            self.assertFalse(is_valid, f"Expected False for invalid token: {token}")
    
    def test_validate_token_no_user(self):
        """Test token validation with no user"""
        token = default_token_generator.make_token(self.user)
        is_valid = self.service.validate_token(None, token)
        self.assertFalse(is_valid)