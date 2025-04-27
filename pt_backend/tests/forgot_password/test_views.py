from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from unittest.mock import patch
from rest_framework import status
from pt_backend.authentication import APIKeyAuthentication

class TestPasswordResetView(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='oldpassword123'
        )
        self.reset_url = '/api/auth/password-reset-request/'
        
    # Positive test cases
    @patch('pt_backend.services.PasswordResetService.process_reset_request')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
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
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
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
    
    @patch('pt_backend.services.PasswordResetService.process_reset_request')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
    def test_password_reset_nonexistent_email(self, mock_auth, mock_process_reset):
        """Test password reset request with non-existent email"""
        mock_auth.return_value = (self.user, 'some-token')
        
        # Simulate DoesNotExist exception
        user_model = get_user_model()
        mock_process_reset.side_effect = user_model.DoesNotExist()
        
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
    
    @patch('pt_backend.services.PasswordResetService.process_reset_request')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
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
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
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
    
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
    def test_password_reset_malformed_json(self, mock_auth):
        """Test password reset request with malformed JSON"""
        mock_auth.return_value = (self.user, 'some-token')
        
        response = self.client.post(
            self.reset_url, 
            "this is not valid json",
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('pt_backend.views.logger')
    @patch('pt_backend.services.PasswordResetService.process_reset_request')
    @patch('pt_backend.authentication.APIKeyAuthentication.authenticate')
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