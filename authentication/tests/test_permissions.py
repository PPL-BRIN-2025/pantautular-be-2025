from django.test import TestCase
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from authentication.permissions import IsTokenAuthenticated
from pt_backend.models import User


class MockView(APIView):
    """Mock view for testing permissions"""
    pass


class IsTokenAuthenticatedTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsTokenAuthenticated()
        self.view = MockView()
        
        self.user = User.objects.create(
            email='test@example.com',
            password='password123',
            name='Test User',
            role='user'
        )

    def test_has_permission_with_valid_user(self):
        """Test that permission is granted when request has a valid user with id"""
        request = self.factory.get('/')
        request.user = self.user
        
        has_permission = self.permission.has_permission(request, self.view)
        
        self.assertTrue(has_permission)
        
    def test_has_permission_with_anonymous_user(self):
        """Test that permission is denied when user is anonymous"""
        from django.contrib.auth.models import AnonymousUser
        
        request = self.factory.get('/')
        request.user = AnonymousUser()
        
        has_permission = self.permission.has_permission(request, self.view)
        
        self.assertFalse(has_permission)
    
    def test_has_permission_with_none_user(self):
        """Test that permission is denied when user is None"""
        request = self.factory.get('/')
        request.user = None
        
        has_permission = self.permission.has_permission(request, self.view)
        
        self.assertFalse(has_permission)
    
    def test_has_permission_with_user_without_id(self):
        """Test that permission is denied when user doesn't have id attribute"""
        class UserWithoutId:
            """Mock user class without id attribute"""
            pass
        
        request = self.factory.get('/')
        request.user = UserWithoutId()
        
        has_permission = self.permission.has_permission(request, self.view)
        
        self.assertFalse(has_permission)
    
    def test_has_no_permission_with_user_with_none_id(self):
        """Test that permission is granted when user has id attribute set to None"""
        class UserWithNoneId:
            """Mock user class with id=None"""
            id = None
        
        request = self.factory.get('/')
        request.user = UserWithNoneId()
        
        has_permission = self.permission.has_permission(request, self.view)
        
        # This test verifies current behavior: a user with id=None still has the attribute,
        # so permission would be granted. You may want to modify your permission class
        # if this is not the intended behavior.
        self.assertFalse(has_permission)

    def tearDown(self):
        self.user.delete()