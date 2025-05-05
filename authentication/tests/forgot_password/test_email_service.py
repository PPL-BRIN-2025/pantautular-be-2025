from django.template import TemplateDoesNotExist
from django.test import TestCase
from unittest.mock import patch, MagicMock
from authentication.email_services import (
    BrevoEmailService, DjangoEmailService
)
from django.core.mail import EmailMultiAlternatives
from authentication.tests.forgot_password.mock_email_service import MockEmailService

class TestEmailServices(TestCase):
    """Test cases for all email service implementations"""

    def test_email_handler_chain_building(self):
        """Test that the email handler chain can be built correctly"""
        # Create handlers
        first_handler = MockEmailService()
        second_handler = MockEmailService()
        third_handler = MockEmailService()
        
        # Build chain
        first_handler.set_next(second_handler)
        second_handler.set_next(third_handler)
        
        # Verify chain structure
        self.assertEqual(first_handler._next_handler, second_handler)
        self.assertEqual(second_handler._next_handler, third_handler)
        self.assertIsNone(third_handler._next_handler)

    def test_email_chain_successful_first_handler(self):
        """Test that the chain stops at the first successful handler"""
        # Create handlers
        first_handler = MockEmailService()
        second_handler = MockEmailService()
        
        # Build chain
        first_handler.set_next(second_handler)
        
        # Process email through chain
        first_handler.handle("test@example.com", "https://reset.link")
        
        # First handler should have sent the email
        self.assertEqual(len(first_handler.sent_emails), 1)
        
        # Second handler should not have been called
        self.assertEqual(len(second_handler.sent_emails), 0)

    def test_email_chain_fallback_on_failure(self):
        """Test that the chain falls back to the next handler when the first one fails"""
        # Create handlers
        first_handler = MockEmailService(should_fail=True)
        second_handler = MockEmailService()
        
        # Build chain
        first_handler.set_next(second_handler)
        
        # Process email through chain
        first_handler.handle("test@example.com", "https://reset.link")
        
        # First handler should have failed and not recorded an email
        self.assertEqual(len(first_handler.sent_emails), 0)
        
        # Second handler should have been called
        self.assertEqual(len(second_handler.sent_emails), 1)
        self.assertEqual(second_handler.sent_emails[0]["recipient"], "test@example.com")
        self.assertEqual(second_handler.sent_emails[0]["reset_link"], "https://reset.link")

    def test_email_chain_all_handlers_fail(self):
        """Test that the chain raises an exception when all handlers fail"""
        # Create handlers that will all fail
        first_handler = MockEmailService(should_fail=True)
        second_handler = MockEmailService(should_fail=True)
        
        # Build chain
        first_handler.set_next(second_handler)
        
        # Process email through chain - should raise exception
        with self.assertRaises(Exception):
            first_handler.handle("test@example.com", "https://reset.link")

    @patch('authentication.email_services.BrevoEmailService.send_password_reset_email')
    @patch('authentication.email_services.DjangoEmailService.send_password_reset_email')
    def test_real_email_services_fallback(self, mock_django_send, mock_brevo_send):
        """Test fallback between real email services"""
        # Make Brevo service fail
        mock_brevo_send.side_effect = Exception("Brevo API error")
        
        # Django service succeeds
        mock_django_send.return_value = True
        
        # Create chain with real services
        brevo_service = BrevoEmailService()
        django_service = DjangoEmailService()
        brevo_service.set_next(django_service)
        
        # Process through chain
        result = brevo_service.handle("test@example.com", "https://reset.link")
        
        # Verify both were called in the right order
        mock_brevo_send.assert_called_once()
        mock_django_send.assert_called_once()
        
        # Verify final result
        self.assertTrue(result)

    def test_missing_template_handled_properly(self):
        """Test that missing template is properly detected and reported"""
        service = DjangoEmailService(template_name="nonexistent_template.html")
        
        with patch('authentication.email_services.render_to_string') as mock_render:
            mock_render.side_effect = TemplateDoesNotExist("nonexistent_template.html")
            
            with self.assertRaises(FileNotFoundError):
                service.send_password_reset_email("test@example.com", "https://reset.link")

    @patch('authentication.email_services.os.getenv')
    def test_email_service_environment_fallback(self, mock_getenv):
        """Test that services handle missing environment variables gracefully"""
        # Make environment variables return None
        mock_getenv.return_value = None
        
        # Brevo service should create empty API key
        with patch('authentication.email_services.TransactionalEmailsApi') as mock_api:
            mock_instance = MagicMock()
            mock_api.return_value = mock_instance
            
            brevo = BrevoEmailService()
            self.assertIsNone(brevo.api_key)
            
        # Django service should use a default sender
        django = DjangoEmailService()
        self.assertEqual(django.from_email, "PantauTular <None>")