from django.test import TestCase
from django.contrib.auth.password_validation import ValidationError
from authentication.serializers import ChangePasswordSerializer
from pt_backend.models import User
from django.contrib.auth.hashers import make_password
from unittest.mock import patch

class ChangePasswordSerializerTest(TestCase):

    def setUp(self):
        self.user = User.objects.create(
            name="TestUser",
            email="test@example.com",
            password=make_password("current_password"),
            role="USER"
        )
        self.serializer_context = {'user': self.user}
        
    def test_password_match_validation(self):
        """Test validation when passwords match"""
        data = {
            'current_password': 'current_password',
            'new_password': 'new_secure_password123',
            'confirm_password': 'new_secure_password123'
        }
        
        serializer = ChangePasswordSerializer(data=data, context=self.serializer_context)
        self.assertTrue(serializer.is_valid())
        
    def test_password_mismatch_validation(self):
        """Test validation when confirmation password doesn't match"""
        data = {
            'current_password': 'current_password',
            'new_password': 'new_secure_password123',
            'confirm_password': 'different_password'
        }
        
        serializer = ChangePasswordSerializer(data=data, context=self.serializer_context)
        self.assertFalse(serializer.is_valid())
        self.assertIn('confirm_password', serializer.errors)
        
    @patch('authentication.serializers.validate_password')
    def test_password_strength_validation(self, mock_validate_password):
        """Test password strength validation is called"""
        data = {
            'current_password': 'current_password',
            'new_password': 'weak',  # Not actually weak due to mock
            'confirm_password': 'weak'  # Not actually weak due to mock
        }
        
        serializer = ChangePasswordSerializer(data=data, context=self.serializer_context)
        serializer.is_valid()
        
        # Check that validate_password was called with new_password and user
        mock_validate_password.assert_called_once_with(data['new_password'], self.user)

    @patch('authentication.serializers.validate_password')
    def test_password_strength_validation_fails(self, mock_validate_password):
        """Test when password strength validation fails"""
        mock_validate_password.side_effect = ValidationError(['Password too common.'])
        
        data = {
            'current_password': 'current_password',
            'new_password': 'password123',
            'confirm_password': 'password123'
        }
        
        serializer = ChangePasswordSerializer(data=data, context=self.serializer_context)
        self.assertFalse(serializer.is_valid())