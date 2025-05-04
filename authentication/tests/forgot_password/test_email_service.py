from django.test import TestCase
from unittest.mock import patch, MagicMock
from authentication.email_services import (
    BrevoEmailService, DjangoEmailService
)
from django.core.mail import EmailMultiAlternatives
from authentication.tests.forgot_password.mock_email_service import MockEmailService

class TestEmailServices(TestCase):
    """Test cases for all email service implementations"""
    
    def test_mock_email_service(self):
        """Test that mock email service records emails properly"""
        service = MockEmailService()
        
        service.send_password_reset_email("test@example.com", "https://reset.link", 2)
        
        self.assertEqual(len(service.sent_emails), 1)
        self.assertEqual(service.sent_emails[0]["recipient"], "test@example.com")
        self.assertEqual(service.sent_emails[0]["reset_link"], "https://reset.link")
        self.assertEqual(service.sent_emails[0]["template_id"], 2)
    
    @patch('authentication.email_services.TransactionalEmailsApi')
    @patch('authentication.email_services.ApiClient')
    @patch('authentication.email_services.os.getenv')
    def test_brevo_email_service(self, mock_getenv, mock_api_client, mock_transactional_api):
        """Test Brevo email service implementation"""
        mock_getenv.return_value = "mock-api-key"
        mock_api_instance = mock_transactional_api.return_value
        
        service = BrevoEmailService(sender_name="Test Sender", sender_email="test@sender.com")
        
        service.send_password_reset_email("recipient@example.com", "https://reset.link", 3)
        
        mock_api_instance.send_transac_email.assert_called_once()
        
        send_email_call = mock_api_instance.send_transac_email.call_args[0][0]
        self.assertEqual(send_email_call.to[0]["email"], "recipient@example.com")
        self.assertEqual(send_email_call.sender["name"], "Test Sender")
        self.assertEqual(send_email_call.sender["email"], "test@sender.com")
        self.assertEqual(send_email_call.template_id, 3)
        self.assertEqual(send_email_call.params["reset_link"], "https://reset.link")
    
    @patch('authentication.email_services.render_to_string')
    @patch('authentication.email_services.EmailMultiAlternatives')
    def test_django_email_service(self, mock_email_multi, mock_render_to_string):
        """Test Django email service implementation"""
        mock_render_to_string.return_value = "<html>reset link</html>"
        mock_msg = MagicMock(spec=EmailMultiAlternatives)
        mock_email_multi.return_value = mock_msg

        service = DjangoEmailService()
        service.send_password_reset_email("recipient@example.com", "https://reset.link")

        mock_render_to_string.assert_called_once_with(
            "email_reset_password.html", {"reset_link": "https://reset.link"}
        )
        mock_email_multi.assert_called_once()
        mock_msg.attach_alternative.assert_called_once_with("<html>reset link</html>", "text/html")
        mock_msg.send.assert_called_once()