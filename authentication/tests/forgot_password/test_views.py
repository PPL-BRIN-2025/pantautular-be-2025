from django.test import TestCase, Client
from unittest.mock import patch
from rest_framework import status
from authentication.security import APIKeyAuthentication
from pt_backend.models import User

class TestPasswordResetView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            name='testuser',
            email='test@example.com',
            password='oldpassword123',
            role="TEST ROLE"
        )
        self.reset_url = '/authentication/password-reset-request'
        
    # Positive test cases
    @patch('authentication.services.PasswordResetService.process_reset_request')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_request_successful(self, mock_auth, mock_process_reset):
        """Test successful password reset request"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_process_reset.return_value = True
        
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
        mock_process_reset.assert_called_once_with('test@example.com')
    
    # Negative test cases
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_missing_email(self, mock_auth):
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
    
    @patch('authentication.services.PasswordResetService.process_reset_request')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_nonexistent_email(self, mock_auth, mock_process_reset):
        """Test password reset request with non-existent email"""
        mock_auth.return_value = (self.user, 'some-token')
        
        # Simulate DoesNotExist exception
        mock_process_reset.side_effect = User.DoesNotExist
        
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
    
    @patch('authentication.services.PasswordResetService.process_reset_request')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_unknown_error(self, mock_auth, mock_process_reset):
        """Test password reset request with unknown error"""
        mock_auth.return_value = (self.user, 'some-token')

        # Simulate a general exception
        mock_process_reset.side_effect = Exception("Unknown error")

        response = self.client.post(
            self.reset_url, 
            {'email': 'test@example.com'}, 
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.json())
    
    # Edge cases
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_empty_email(self, mock_auth):
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
    
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_malformed_json(self, mock_auth):
        """Test password reset request with malformed JSON"""
        mock_auth.return_value = (self.user, 'some-token')
        
        response = self.client.post(
            self.reset_url, 
            "this is not valid json",
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('authentication.views.logger')
    @patch('authentication.services.PasswordResetService.process_reset_request')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_password_reset_logs_error(self, mock_auth, mock_process_reset, mock_logger):
        """Test that errors are properly logged"""
        mock_auth.return_value = (self.user, 'some-token')
        
        error = Exception("Test error")
        mock_process_reset.side_effect = error
        
        response = self.client.post(
            self.reset_url, 
            {'email': 'test@example.com'}, 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        mock_logger.error.assert_called_once()

class TestPasswordResetValidateView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            name='testuser',
            email='test@example.com',
            password='oldpassword123',
            role="TEST ROLE"
        )
        self.validate_url_base = '/authentication/password-reset-validate'
        self.valid_uidb64 = 'valid-uid'
        self.valid_token = 'valid-token'
        self.valid_url = f"{self.validate_url_base}/{self.valid_uidb64}/{self.valid_token}"
        
    # Positive test case
    @patch('authentication.services.PasswordResetService.validate_token')
    @patch('authentication.services.PasswordResetService.get_user_from_uidb64')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_validate_token_successful(self, mock_auth, mock_get_user, mock_validate):
        """Test successful token validation"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_get_user.return_value = self.user
        mock_validate.return_value = True
        
        response = self.client.get(
            self.valid_url,
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('valid', response.json())
        self.assertTrue(response.json()['valid'])
        mock_get_user.assert_called_once_with(self.valid_uidb64)
        mock_validate.assert_called_once_with(self.user, self.valid_token)
    
    # Negative test cases
    @patch('authentication.services.PasswordResetService.get_user_from_uidb64')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_validate_token_user_not_found(self, mock_auth, mock_get_user):
        """Test token validation with non-existent user"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_get_user.return_value = None
        
        response = self.client.get(
            self.valid_url,
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('valid', response.json())
        self.assertFalse(response.json()['valid'])
        mock_get_user.assert_called_once_with(self.valid_uidb64)
    
    @patch('authentication.services.PasswordResetService.validate_token')
    @patch('authentication.services.PasswordResetService.get_user_from_uidb64')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_validate_token_invalid_token(self, mock_auth, mock_get_user, mock_validate):
        """Test token validation with invalid token"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_get_user.return_value = self.user
        mock_validate.return_value = False
        
        response = self.client.get(
            self.valid_url,
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('valid', response.json())
        self.assertFalse(response.json()['valid'])
        mock_get_user.assert_called_once_with(self.valid_uidb64)
        mock_validate.assert_called_once_with(self.user, self.valid_token)
    
    # Edge cases
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_validate_token_empty_uidb64(self, mock_auth):
        """Test token validation with empty uidb64"""
        mock_auth.return_value = (self.user, 'some-token')
        
        url = f"{self.validate_url_base}//valid-token"
        
        response = self.client.get(
            url,
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_validate_token_empty_token(self, mock_auth):
        """Test token validation with empty token"""
        mock_auth.return_value = (self.user, 'some-token')
        
        url = f"{self.validate_url_base}/valid-uid/"
        
        response = self.client.get(
            url,
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @patch('authentication.services.PasswordResetService.validate_token')
    @patch('authentication.services.PasswordResetService.get_user_from_uidb64')
    @patch('authentication.security.APIKeyAuthentication.authenticate')
    def test_validate_token_special_chars(self, mock_auth, mock_get_user, mock_validate):
        """Test token validation with special characters in token"""
        mock_auth.return_value = (self.user, 'some-token')
        mock_get_user.return_value = self.user
        mock_validate.return_value = True
        
        special_token = "abc-_.~+*"
        special_url = f"{self.validate_url_base}/{self.valid_uidb64}/{special_token}"
        
        response = self.client.get(
            special_url,
            HTTP_X_API_KEY='test-api-key'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('valid', response.json())
        self.assertTrue(response.json()['valid'])
        mock_validate.assert_called_once_with(self.user, special_token)