from django.test import TestCase
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from unittest.mock import patch, Mock, MagicMock
from authentication.services import PasswordResetService, ChangePasswordService
from django.contrib.auth.hashers import check_password, make_password
from pt_backend.models import User
from authentication.services import ChangePasswordService

class ChangePasswordServiceTest(TestCase):

    def test_change_password_success(self):
        user = User.objects.create(name="Charlie", email="charlie@example.com", password="oldpass", role="USER") # NOSONAR – test data, not a real secret
        service = ChangePasswordService()
        result = service.change_password("charlie@example.com", "newsecurepass")

        user.refresh_from_db()
        self.assertTrue(result)
        self.assertTrue(check_password("newsecurepass", user.password)) # NOSONAR – test data, not a real secret

    def test_change_password_user_not_found(self):
        service = ChangePasswordService()
        result = service.change_password("ghost@example.com", "pass")
        self.assertFalse(result)

    def test_change_password_empty_password(self):
        user = User.objects.create(name="Dana", email="dana@example.com", password="oldpass", role="USER") # NOSONAR – test data, not a real secret
        service = ChangePasswordService()
        result = service.change_password("dana@example.com", "")

        user.refresh_from_db()
        self.assertTrue(result)
        self.assertTrue(check_password("", user.password)) # NOSONAR – test data, not a real secret

    def test_change_password_reuse_same_password(self):
        user = User.objects.create(name="Eli", email="eli@example.com", password="oldpass", role="USER") # NOSONAR – test data, not a real secret
        service = ChangePasswordService()
        result = service.change_password("eli@example.com", "oldpass")

        user.refresh_from_db()
        self.assertTrue(result)
        self.assertTrue(check_password("oldpass", user.password))  # NOSONAR – test data, not a real secret

class UpdateUserPasswordTest(TestCase):
    
    def setUp(self):
        self.service = ChangePasswordService()
        self.user = User.objects.create(
            name="TestUser",
            email="test@example.com",
            password=make_password("current_password"),  # NOSONAR - test data
            role="USER"
        )
        
    def test_update_password_success(self):
        """Test successful password update"""
        result = self.service.update_user_password(
            self.user, 
            "current_password",  # NOSONAR - test data
            "new_secure_password"  # NOSONAR - test data
        )
        
        self.user.refresh_from_db()
        self.assertTrue(result["success"])
        self.assertTrue(check_password("new_secure_password", self.user.password)) # NOSONAR - test data
        
    def test_update_password_incorrect_current_password(self):
        """Test failure when current password is incorrect"""
        result = self.service.update_user_password(
            self.user, 
            "wrong_password",  # NOSONAR - test data
            "new_secure_password"  # NOSONAR - test data
        )
        
        self.user.refresh_from_db()
        self.assertFalse(result["success"])
        self.assertTrue(check_password("current_password", self.user.password)) # NOSONAR - test data
        self.assertFalse(check_password("new_secure_password", self.user.password)) # NOSONAR - test data