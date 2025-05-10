from django.test import TestCase, Client
from unittest.mock import patch, MagicMock
from rest_framework import status
from authentication.security import APIKeyAuthentication
from pt_backend.models import User
from rest_framework.exceptions import ParseError

class TestPasswordResetLinkRequestView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            name='testuser',
            email='test@example.com',
            password='oldpassword123',
            role="TEST ROLE"
        )
        self.reset_url = '/authentication/password-reset-request'
    
    @patch('authentication.views.UserRepository')
    @patch('authentication.views.UserFinderService')
    @patch('authentication.views.PasswordTokenService')
    @patch('authentication.views.ResetLinkService')
    @patch('authentication.views.PasswordResetService')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_view_initialization(self, mock_auth, mock_reset_service, mock_link_service, 
                                 mock_token_service, mock_finder_service, mock_repository):
        """Test proper initialization of services in view"""
        # Setup mocks
        mock_auth.return_value = (self.user, 'some-token')
        mock_repo_instance = MagicMock()
        mock_repository.return_value = mock_repo_instance
        mock_finder_instance = MagicMock()
        mock_finder_service.return_value = mock_finder_instance
        mock_token_instance = MagicMock()
        mock_token_service.return_value = mock_token_instance
        mock_link_instance = MagicMock()
        mock_link_service.return_value = mock_link_instance
        mock_reset_instance = MagicMock()
        mock_reset_service.return_value = mock_reset_instance
        mock_reset_instance.initiate_password_reset.return_value = True
        
        # Make request to trigger view initialization
        response = self.client.post(
            self.reset_url, 
            {'email': 'test@example.com'}, 
            content_type='application/json'
        )
        
        # Verify services were initialized properly
        mock_repository.assert_called_once()
        mock_finder_service.assert_called_once_with(mock_repo_instance)
        mock_token_service.assert_called_once_with(mock_repo_instance)
        mock_link_service.assert_called_once()
        mock_reset_service.assert_called_once_with(
            user_finder=mock_finder_instance,
            password_token_service=mock_token_instance,
            reset_link_service=mock_link_instance
        )
        
        # Verify email was passed to the service
        mock_reset_instance.initiate_password_reset.assert_called_once_with('test@example.com')
        
        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.json())
    
    @patch('authentication.views.PasswordResetService.initiate_password_reset')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_successful_password_reset_request(self, mock_auth, mock_initiate_reset):
        """Test successful password reset request"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_initiate_reset.return_value = True
        
        response = self.client.post(
            self.reset_url, 
            {'email': 'test@example.com'}, 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.json())
        self.assertEqual(
            response.json()['message'], 
            "Jika akunmu terdaftar, kami sudah mengirim link untuk mereset password akun Anda"
        )
        mock_initiate_reset.assert_called_once_with('test@example.com')
    
    @patch('authentication.views.PasswordResetService.initiate_password_reset')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_failed_password_reset_request(self, mock_auth, mock_initiate_reset):
        """Test when reset service returns False"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_initiate_reset.return_value = False
        
        response = self.client.post(
            self.reset_url, 
            {'email': 'test@example.com'}, 
            content_type='application/json'
        )
        
        # Should still return 200 with generic message for security
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.json())
        mock_initiate_reset.assert_called_once_with('test@example.com')
    
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_missing_email(self, mock_auth):
        """Test password reset request with missing email"""
        mock_auth.return_value = (self.user, 'some-token')
        
        response = self.client.post(
            self.reset_url, 
            {}, 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.json())
        self.assertEqual(response.json()['error'], "Email is required")
    
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_empty_email(self, mock_auth):
        """Test password reset request with empty email string"""
        mock_auth.return_value = (self.user, 'some-token')
        
        response = self.client.post(
            self.reset_url, 
            {'email': ''}, 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.json())
        self.assertEqual(response.json()['error'], "Email is required")
    
    @patch('authentication.views.PasswordResetService.initiate_password_reset')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_user_does_not_exist(self, mock_auth, mock_initiate_reset):
        """Test handling User.DoesNotExist exception"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_initiate_reset.side_effect = User.DoesNotExist
        
        response = self.client.post(
            self.reset_url, 
            {'email': 'nonexistent@example.com'}, 
            content_type='application/json'
        )
        
        # Should still return 200 to prevent email enumeration
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.json())
        self.assertEqual(
            response.json()['message'], 
            "Jika akunmu terdaftar, kami sudah mengirim link untuk mereset password akun Anda"
        )
    
    @patch('rest_framework.request.Request.data')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_parse_error_handling(self, mock_auth, mock_data):
        """Test handling ParseError exception"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_data.get.side_effect = ParseError("Invalid JSON")
        
        response = self.client.post(
            self.reset_url, 
            "this is not valid json",
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.json())
    
    @patch('authentication.views.logger')
    @patch('authentication.views.PasswordResetService.initiate_password_reset')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_generic_exception_handling(self, mock_auth, mock_initiate_reset, mock_logger):
        """Test handling generic exceptions"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_initiate_reset.side_effect = ValueError("Some unexpected error")
        
        response = self.client.post(
            self.reset_url, 
            {'email': 'test@example.com'}, 
            content_type='application/json'
        )
        
        # Verify error was logged
        mock_logger.error.assert_called_once()
        
        # Verify response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.json())
        self.assertEqual(response.json()['error'], "An unexpected error occurred. Please try again later.")

class TestPasswordResetLinkValidateView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            name='testuser',
            email='test@example.com',
            password='oldpassword123',
            role="TEST ROLE"
        )
        self.validate_url_base = '/authentication/password-reset-validate'
    
    @patch('authentication.views.UserRepository')
    @patch('authentication.views.UserFinderService')
    @patch('authentication.views.PasswordTokenService')
    @patch('authentication.views.ResetLinkService')
    @patch('authentication.views.PasswordResetService')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_view_initialization(self, mock_auth, mock_reset_service, mock_link_service, 
                                 mock_token_service, mock_finder_service, mock_repository):
        """Test proper initialization of services in view"""
        # Setup mocks
        mock_auth.return_value = (self.user, 'some-token')
        mock_repo_instance = MagicMock()
        mock_repository.return_value = mock_repo_instance
        mock_finder_instance = MagicMock()
        mock_finder_service.return_value = mock_finder_instance
        mock_token_instance = MagicMock()
        mock_token_service.return_value = mock_token_instance
        mock_link_instance = MagicMock()
        mock_link_service.return_value = mock_link_instance
        mock_reset_instance = MagicMock()
        mock_reset_service.return_value = mock_reset_instance
        mock_reset_instance.verify_reset_attempt.return_value = self.user
        
        # Make request to trigger view initialization
        response = self.client.get(
            f"{self.validate_url_base}/someuid/sometoken"
        )
        
        # Verify services were initialized properly
        mock_repository.assert_called_once()
        mock_finder_service.assert_called_once_with(mock_repo_instance)
        mock_token_service.assert_called_once_with(mock_repo_instance)
        mock_link_service.assert_called_once()
        mock_reset_service.assert_called_once_with(
            user_finder=mock_finder_instance,
            password_token_service=mock_token_instance,
            reset_link_service=mock_link_instance
        )
        
        # Verify uidb64 and token were passed to the service
        mock_reset_instance.verify_reset_attempt.assert_called_once_with('someuid', 'sometoken')
        
        # Verify response for valid user
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"valid": True})
    
    @patch('authentication.views.PasswordResetService.verify_reset_attempt')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_valid_token(self, mock_auth, mock_verify_attempt):
        """Test validation with valid token"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_verify_attempt.return_value = self.user
        
        response = self.client.get(
            f"{self.validate_url_base}/validuid/validtoken"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"valid": True})
        mock_verify_attempt.assert_called_once_with('validuid', 'validtoken')
    
    @patch('authentication.views.PasswordResetService.verify_reset_attempt')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_invalid_token(self, mock_auth, mock_verify_attempt):
        """Test validation with invalid token"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_verify_attempt.return_value = None
        
        response = self.client.get(
            f"{self.validate_url_base}/invaliduid/invalidtoken"
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"valid": False})
        mock_verify_attempt.assert_called_once_with('invaliduid', 'invalidtoken')

class TestPasswordResetConfirmView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            name='testuser',
            email='test@example.com',
            password='oldpassword123',
            role="TEST ROLE"
        )
        self.confirm_url_base = '/authentication/password-reset-confirm'
        self.valid_uidb64 = 'valid-uid'
        self.valid_token = 'valid-token'
        self.valid_url = f"{self.confirm_url_base}/{self.valid_uidb64}/{self.valid_token}"
        
        # Valid password that meets all requirements
        self.valid_password = "TestPass123!" # NOSONAR – test data, not a real secret
        self.valid_data = {
            'password': self.valid_password,
            'password-confirm': self.valid_password
        }
    
    
    @patch('authentication.services.ChangePasswordService.change_password')
    @patch('authentication.services.PasswordTokenService.validate_token')
    @patch('authentication.services.PasswordTokenService.get_user_from_uidb64')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_confirm_successful(self, mock_auth, mock_get_user, mock_validate, mock_change_password):
        """Test successful password reset confirmation"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_get_user.return_value = self.user
        mock_validate.return_value = True
        mock_change_password.return_value = True
        
        response = self.client.post(
            self.valid_url,
            self.valid_data,
            content_type='application/json',
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.json())
        self.assertEqual(response.json()['detail'], "Password berhasil diganti")
        mock_get_user.assert_called_once_with(self.valid_uidb64)
        mock_validate.assert_called_once_with(self.user, self.valid_token)
        mock_change_password.assert_called_once_with(self.user.email, self.valid_password)

    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_confirm_missing_password(self, mock_auth):
        """Test password reset confirmation with missing password"""
        mock_auth.return_value = (self.user, 'some-token')
        
        response = self.client.post(
            self.valid_url,
            {'password-confirm': self.valid_password},
            content_type='application/json',
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.json())
        self.assertEqual(response.json()['detail'], "Password diperlukan")
    
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_confirm_missing_confirm_password(self, mock_auth):
        """Test password reset confirmation with missing confirm password"""
        mock_auth.return_value = (self.user, 'some-token')
        
        response = self.client.post(
            self.valid_url,
            {'password': self.valid_password},
            content_type='application/json',
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.json())
        self.assertEqual(response.json()['detail'], "Konfirmasi password diperlukan")
    
    @patch('authentication.services.PasswordValidationService.validate_password_match')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_confirm_passwords_dont_match(self, mock_auth, mock_validate_match):
        """Test password reset confirmation with non-matching passwords"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_validate_match.return_value = False
        
        data = {
            'password': 'Password123!',
            'password-confirm': 'DifferentPassword123!'
        }
        
        response = self.client.post(
            self.valid_url,
            data,
            content_type='application/json',
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.json())
        self.assertEqual(response.json()['detail'], "Password tidak cocok")
    
    @patch('authentication.services.PasswordValidationService.validate_password_strength')
    @patch('authentication.services.PasswordValidationService.validate_password_match')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_confirm_weak_password(self, mock_auth, mock_validate_match, mock_validate_strength):
        """Test password reset confirmation with weak password"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_validate_match.return_value = True
        mock_validate_strength.return_value = (False, "Password harus mengandung minimal 1 huruf besar")
        
        data = {
            'password': 'weakpassword123!',
            'password-confirm': 'weakpassword123!'
        }
        
        response = self.client.post(
            self.valid_url,
            data,
            content_type='application/json',
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.json())
        self.assertEqual(response.json()['detail'], "Password harus mengandung minimal 1 huruf besar")
    
    @patch('authentication.services.PasswordTokenService.get_user_from_uidb64')
    @patch('authentication.services.PasswordValidationService.validate_password_strength')
    @patch('authentication.services.PasswordValidationService.validate_password_match')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_confirm_user_not_found(self, mock_auth, mock_validate_match, mock_validate_strength, mock_get_user):
        """Test password reset confirmation with non-existent user"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_validate_match.return_value = True
        mock_validate_strength.return_value = (True, "")
        mock_get_user.return_value = None
        
        response = self.client.post(
            self.valid_url,
            self.valid_data,
            content_type='application/json',
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.json())
        self.assertEqual(response.json()['detail'], "Link tidak valid")
    
    @patch('authentication.services.PasswordTokenService.validate_token')
    @patch('authentication.services.PasswordTokenService.get_user_from_uidb64')
    @patch('authentication.services.PasswordValidationService.validate_password_strength')
    @patch('authentication.services.PasswordValidationService.validate_password_match')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_confirm_invalid_token(self, mock_auth, mock_validate_match, mock_validate_strength, mock_get_user, mock_validate_token):
        """Test password reset confirmation with invalid token"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_validate_match.return_value = True
        mock_validate_strength.return_value = (True, "")
        mock_get_user.return_value = self.user
        mock_validate_token.return_value = False
        
        response = self.client.post(
            self.valid_url,
            self.valid_data,
            content_type='application/json',
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.json())
        self.assertEqual(response.json()['detail'], "Token tidak valid atau sudah kedaluwarsa")
    
    @patch('authentication.services.ChangePasswordService.change_password')
    @patch('authentication.services.PasswordTokenService.validate_token')
    @patch('authentication.services.PasswordTokenService.get_user_from_uidb64')
    @patch('authentication.services.PasswordValidationService.validate_password_strength')
    @patch('authentication.services.PasswordValidationService.validate_password_match')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_confirm_change_password_failed(self, mock_auth, mock_validate_match, mock_validate_strength, 
                                                         mock_get_user, mock_validate_token, mock_change_password):
        """Test password reset confirmation with change password failure"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_validate_match.return_value = True
        mock_validate_strength.return_value = (True, "")
        mock_get_user.return_value = self.user
        mock_validate_token.return_value = True
        mock_change_password.return_value = False
        
        response = self.client.post(
            self.valid_url,
            self.valid_data,
            content_type='application/json',
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.json())
        self.assertEqual(response.json()['detail'], "Gagal mengganti password")
        
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_confirm_empty_uidb64(self, mock_auth):
        """Test password reset confirmation with empty uidb64"""
        mock_auth.return_value = (self.user, 'some-token')
        
        url = f"{self.confirm_url_base}//valid-token"
        
        response = self.client.post(
            url,
            self.valid_data,
            content_type='application/json',
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_confirm_empty_token(self, mock_auth):
        """Test password reset confirmation with empty token"""
        mock_auth.return_value = (self.user, 'some-token')
        
        url = f"{self.confirm_url_base}/valid-uid/"
        
        response = self.client.post(
            url,
            self.valid_data,
            content_type='application/json',
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @patch('authentication.services.PasswordValidationService.validate_password_strength')
    @patch('authentication.services.PasswordValidationService.validate_password_match')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_confirm_password_strength_validation(self, mock_auth, mock_validate_match, mock_validate_strength):
        """Test different password strength validation error messages"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_validate_match.return_value = True
        
        error_messages = [
            "Password harus minimal 8 karakter",
            "Password harus mengandung minimal 1 huruf besar",
            "Password harus mengandung minimal 1 huruf kecil",
            "Password harus mengandung minimal 1 angka",
            "Password harus mengandung minimal 1 karakter spesial"
        ]
        
        for error_message in error_messages:
            mock_validate_strength.return_value = (False, error_message)
            
            response = self.client.post(
                self.valid_url,
                self.valid_data,
                content_type='application/json',
                HTTP_X_API_KEY='test-api-key'
            )
            
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('detail', response.json())
            self.assertEqual(response.json()['detail'], error_message)
    
    @patch('authentication.services.PasswordTokenService.validate_token')
    @patch('authentication.services.PasswordTokenService.get_user_from_uidb64')
    @patch('authentication.services.PasswordValidationService.validate_password_strength')
    @patch('authentication.services.PasswordValidationService.validate_password_match')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_confirm_special_chars(self, mock_auth, mock_validate_match, mock_validate_strength, 
                                                mock_get_user, mock_validate_token):
        """Test password reset confirmation with special characters in token"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_validate_match.return_value = True
        mock_validate_strength.return_value = (True, "")
        mock_get_user.return_value = self.user
        mock_validate_token.return_value = True
        
        special_token = "abc-_.~+*"
        special_url = f"{self.confirm_url_base}/{self.valid_uidb64}/{special_token}"
        
        with patch('authentication.services.ChangePasswordService.change_password', return_value=True):
            response = self.client.post(
                special_url,
                self.valid_data,
                content_type='application/json',
                HTTP_X_API_KEY='test-api-key'
            )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_validate_token.assert_called_once_with(self.user, special_token)