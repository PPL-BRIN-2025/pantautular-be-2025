from django.test import TestCase
from authentication.serializers import LoginSerializer

class LoginSerializerTests(TestCase):
    def test_valid_data(self):
        """Test serializer with valid data - happy path"""
        data = {
            'email': 'test@example.com',
            'password': 'Password123!' # NOSONAR – test data, not a real secret
        }
        serializer = LoginSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['email'], 'test@example.com')
        self.assertEqual(serializer.validated_data['password'], 'Password123!')

    def test_missing_email(self):
        """Test serializer with missing email - unhappy path"""
        data = {
            'password': 'Password123!' # NOSONAR – test data, not a real secret
        }
        serializer = LoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_missing_password(self):
        """Test serializer with missing password - unhappy path"""
        data = {
            'email': 'test@example.com'
        }
        serializer = LoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_invalid_email_format(self):
        """Test serializer with invalid email format - edge case"""
        data = {
            'email': 'not-an-email',
            'password': 'Password123!' # NOSONAR – test data, not a real secret
        }
        serializer = LoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_password_too_short(self):
        """Test serializer with password too short - edge case"""
        data = {
            'email': 'test@example.com',
            'password': 'short' # NOSONAR – test data, not a real secret
        }
        serializer = LoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)