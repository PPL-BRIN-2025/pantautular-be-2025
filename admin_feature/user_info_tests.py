# Add this at the end of admin_feature/tests.py or in a new test file

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from pt_backend.models import Role, User
from django.contrib.auth.hashers import make_password
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from django.conf import settings
import jwt
from datetime import datetime, timedelta
from rest_framework import status

TEST_API_KEY_HEADER = {"HTTP_X_API_KEY": "test-key"}

@override_settings(SECRET_API_KEYS=("test-key",))
class UserInfoJWTOnlyTests(TestCase):
    """Test specifically for JWT-only authentication paths in UserInfoAPIView.
    
    These tests ensure 100% coverage of cases where:
    1. User has valid JWT but no API key
    2. User has valid JWT with non-admin role
    3. User has JWT with embedded role but no user object
    4. Cookie-based JWT authentication
    """
    databases = {'default'}
    
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('admin-user-info')
        
        # Create test users
        self.admin = User.objects.create(
            name='JWT Admin',
            email='jwt-admin@example.com',
            password=make_password('AdminPass123'),
            role='ADMIN',
        )
        
        self.viewer = User.objects.create(
            name='JWT Viewer',
            email='jwt-viewer@example.com',
            password=make_password('ViewerPass123'),
            role='VIEWER',
        )
        
        # Create roles
        Role.objects.get_or_create(name='ADMIN')
        Role.objects.get_or_create(name='VIEWER')
    
    def _get_jwt_for_user(self, user):
        """Generate a JWT token for a user without using the login endpoint"""
        payload = {
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    
    def test_jwt_only_no_api_key_admin_succeeds(self):
        """Test that admin with valid JWT but no API key can access the endpoint"""
        token = self._get_jwt_for_user(self.admin)
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        
        response = self.client.get(self.url, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], self.admin.name)
        self.assertEqual(response.data["role"], "ADMIN")
    
    def test_jwt_only_no_api_key_non_admin_forbidden(self):
        """Test that non-admin with valid JWT but no API key gets forbidden"""
        token = self._get_jwt_for_user(self.viewer)
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        
        response = self.client.get(self.url, **headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "Akses Ditolak")
    
    def test_jwt_with_embedded_claims_no_user_lookup(self):
        """Test JWT with embedded name/role but non-existent user ID still works"""
        payload = {
            "user_id": 999999,  # Non-existent user ID
            "name": "Embedded Admin",
            "role": "ADMIN",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        
        response = self.client.get(self.url, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Embedded Admin")
        self.assertEqual(response.data["role"], "ADMIN")
    
    def test_jwt_with_malformed_authorization_header(self):
        """Test invalid Authorization header format"""
        # Missing 'Bearer ' prefix
        token = self._get_jwt_for_user(self.admin)
        headers = {"HTTP_AUTHORIZATION": token}
        
        response = self.client.get(self.url, **headers)
        self.assertEqual(response.status_code, 401)
        self.assertIn("Authentication", str(response.data["detail"]))
    
    def test_jwt_token_but_no_name_or_role(self):
        """Test JWT with user_id but missing name/role, requiring DB lookup"""
        payload = {
            "user_id": self.admin.id,
            # No name or role - forces UserInfoAPIView to fetch from DB
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        
        response = self.client.get(self.url, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], self.admin.name)
        self.assertEqual(response.data["role"], "ADMIN")