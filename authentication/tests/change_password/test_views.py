from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.hashers import make_password, check_password
from pt_backend.models import User
from unittest.mock import patch, PropertyMock

class ChangePasswordViewTest(TestCase):
    
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('change-password')  # Pastikan nama URL sesuai dengan yang ada di urls.py
        
        # Buat user untuk test
        self.user = User.objects.create(
            name="TestUser",
            email="test@example.com",
            password=make_password("current_password"),  # NOSONAR - test data
            role="USER"
        )
        
        # Simulasi APIKeyAuthentication
        self.patcher = patch('authentication.security.APIKeyAuthentication.authenticate')
        self.mock_auth = self.patcher.start()
        self.mock_auth.return_value = (self.user, None)
    
    def tearDown(self):
        self.patcher.stop()
    
    # def test_change_password_success(self):
    #     # Mock update_user_password untuk mengembalikan success
    #     with patch('authentication.services.ChangePasswordService.update_user_password') as mock_update:
    #         mock_update.return_value = {"success": True, "message": "Password successfully updated"}
            
    #         data = {
    #             'current_password': 'current_password',  # NOSONAR - test data
    #             'new_password': 'new_secure_password',  # NOSONAR - test data
    #             'confirm_password': 'new_secure_password'  # NOSONAR - test data
    #         }
            
    #         # Mock serializer is_valid dan validated_data
    #         with patch('authentication.serializers.ChangePasswordSerializer.is_valid') as mock_is_valid:
    #             mock_is_valid.return_value = True
                
    #             with patch('authentication.serializers.ChangePasswordSerializer.validated_data', 
    #                     new_callable=PropertyMock) as mock_validated_data:
    #                 mock_validated_data.return_value = {
    #                     'current_password': 'current_password',
    #                     'new_password': 'new_secure_password'
    #                 }
                    
    #                 response = self.client.post(self.url, data, format='json')
                    
    #                 # Check response
    #                 self.assertEqual(response.status_code, status.HTTP_200_OK)
    #                 self.assertIn('message', response.data)
    
    # def test_change_password_incorrect_current(self):
    #     """Test dengan password saat ini salah"""
    #     # Mock update_user_password untuk mengembalikan error
    #     with patch('authentication.services.ChangePasswordService.update_user_password') as mock_update:
    #         mock_update.return_value = {"success": False, "error": "Current password is incorrect"}
            
    #         data = {
    #             'current_password': 'wrong_password',  # NOSONAR - test data
    #             'new_password': 'new_secure_password',  # NOSONAR - test data
    #             'confirm_password': 'new_secure_password'  # NOSONAR - test data
    #         }
            
    #         # Mock serializer is_valid dan validated_data
    #         with patch('authentication.serializers.ChangePasswordSerializer.is_valid') as mock_is_valid:
    #             mock_is_valid.return_value = True
                
    #             with patch('authentication.serializers.ChangePasswordSerializer.validated_data', 
    #                     new_callable=PropertyMock) as mock_validated_data:
    #                 mock_validated_data.return_value = {
    #                     'current_password': 'wrong_password',
    #                     'new_password': 'new_secure_password'
    #                 }
                    
    #                 response = self.client.post(self.url, data, format='json')
                    
    #                 # Check response
    #                 self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #                 self.assertIn('error', response.data)
    
    
    def test_change_password_no_auth(self):
        """Test tanpa autentikasi"""
        # Atur mock untuk simulasi tidak ada autentikasi
        self.mock_auth.return_value = None
        
        data = {
            'current_password': 'current_password',  # NOSONAR - test data
            'new_password': 'new_secure_password',  # NOSONAR - test data
            'confirm_password': 'new_secure_password'  # NOSONAR - test data
        }
        
        response = self.client.post(self.url, data, format='json')
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    # def test_change_password_serializer_error(self):
    #     """Test ketika serializer mengembalikan error"""
    #     # Mock serializer is_valid untuk mengembalikan False
    #     with patch('authentication.serializers.ChangePasswordSerializer.is_valid') as mock_is_valid:
    #         mock_is_valid.return_value = False
            
    #         # Mock serializer errors
    #         with patch('authentication.serializers.ChangePasswordSerializer.errors', 
    #                 new_callable=PropertyMock) as mock_errors:
    #             mock_errors.return_value = {"confirm_password": ["Password confirmation does not match."]}
                
    #             data = {
    #                 'current_password': 'current_password',  # NOSONAR - test data
    #                 'new_password': 'new_secure_password',  # NOSONAR - test data
    #                 'confirm_password': 'different_password'  # NOSONAR - test data
    #             }
                
    #             response = self.client.post(self.url, data, format='json')
                
    #             # Check response
    #             self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #             self.assertIn('confirm_password', response.data)
    
    # def test_change_password_exception(self):
    #     """Test ketika terjadi exception"""
    #     with patch('authentication.serializers.ChangePasswordSerializer.is_valid') as mock:
    #         mock.side_effect = Exception("Test exception")
            
    #         data = {
    #             'current_password': 'current_password',  # NOSONAR - test data
    #             'new_password': 'new_secure_password',  # NOSONAR - test data
    #             'confirm_password': 'new_secure_password'  # NOSONAR - test data
    #         }
            
    #         response = self.client.post(self.url, data, format='json')
            
    #         # Check response
    #         self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    #         self.assertIn('error', response.data)