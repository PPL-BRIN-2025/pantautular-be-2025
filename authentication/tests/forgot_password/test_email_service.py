from django.template import TemplateDoesNotExist
from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.core.mail import EmailMultiAlternatives

from authentication.email_services import (
    EmailContentStrategy, PasswordResetEmailStrategy, 
    EmailProvider, EmailService, 
    BrevoEmailProvider, DjangoEmailProvider
)

class MockEmailProvider(EmailProvider):
    """Mock provider for testing"""
    def __init__(self, should_fail=False):
        self.sent_emails = []
        self.should_fail = should_fail
        
    def send_email(self, recipient_email, subject, template_name, context):
        if self.should_fail:
            raise RuntimeError("Mock provider failure")
            
        self.sent_emails.append({
            "recipient": recipient_email,
            "subject": subject,
            "template": template_name,
            "context": context
        })
        return True

class CustomEmailStrategy(EmailContentStrategy):
    """Custom strategy for testing"""
    def get_subject(self):
        return "Custom Subject"
    
    def get_template_name(self):
        return "custom_template.html"
    
    def get_context_data(self, **kwargs):
        return {"custom_data": kwargs.get('custom_value', 'default')}

class TestEmailService(TestCase):
    """Test cases for the new email service implementation"""
    
    def setUp(self):
        self.reset_strategy = PasswordResetEmailStrategy()
        self.custom_strategy = CustomEmailStrategy()
    
    def test_password_reset_strategy(self):
        """Test the password reset email strategy"""
        # Check basic properties
        self.assertEqual(self.reset_strategy.get_subject(), "Password Reset Request")
        self.assertEqual(self.reset_strategy.get_template_name(), "email_reset_password.html")
        
        # Check context data with valid input
        context = self.reset_strategy.get_context_data(reset_link="https://example.com/reset")
        self.assertEqual(context, {"reset_link": "https://example.com/reset"})
        
        # Check validation when reset_link is missing
        with self.assertRaises(ValueError):
            self.reset_strategy.get_context_data()
    
    def test_custom_strategy(self):
        """Test a custom email strategy"""
        # Check custom strategy properties
        self.assertEqual(self.custom_strategy.get_subject(), "Custom Subject")
        self.assertEqual(self.custom_strategy.get_template_name(), "custom_template.html")
        
        # Test with custom value
        context = self.custom_strategy.get_context_data(custom_value="test-value")
        self.assertEqual(context, {"custom_data": "test-value"})
        
        # Test with default value
        context = self.custom_strategy.get_context_data()
        self.assertEqual(context, {"custom_data": "default"})
    
    def test_email_service_initialization(self):
        """Test email service initializes correctly"""
        # Test with default providers
        service = EmailService()
        self.assertEqual(len(service.providers), 2)
        self.assertIsInstance(service.providers[0], BrevoEmailProvider)
        self.assertIsInstance(service.providers[1], DjangoEmailProvider)
        
        # Test with custom providers
        provider1 = MockEmailProvider()
        provider2 = MockEmailProvider()
        service = EmailService(providers=[provider1, provider2])
        self.assertEqual(len(service.providers), 2)
        self.assertEqual(service.providers[0], provider1)
        self.assertEqual(service.providers[1], provider2)
    
    def test_email_service_successful_send(self):
        """Test email service sends successfully with first provider"""
        # Create providers
        provider1 = MockEmailProvider()
        provider2 = MockEmailProvider()
        
        # Create service with mock providers
        service = EmailService(providers=[provider1, provider2])
        
        # Send email
        result = service.send_email(
            recipient_email="test@example.com",
            strategy=self.reset_strategy,
            reset_link="https://example.com/reset"
        )
        
        # First provider should have sent the email
        self.assertEqual(len(provider1.sent_emails), 1)
        if provider1.sent_emails:
            self.assertEqual(provider1.sent_emails[0]["recipient"], "test@example.com")
            self.assertEqual(provider1.sent_emails[0]["subject"], "Password Reset Request")
            self.assertEqual(provider1.sent_emails[0]["template"], "email_reset_password.html")
            self.assertEqual(provider1.sent_emails[0]["context"], {"reset_link": "https://example.com/reset"})
        
        # Second provider should not have been called
        self.assertEqual(len(provider2.sent_emails), 0)
        
        # Result should be True
        self.assertTrue(result)
    
    def test_email_service_fallback(self):
        """Test email service falls back to next provider when first fails"""
        # Create providers - first will fail
        provider1 = MockEmailProvider(should_fail=True)
        provider2 = MockEmailProvider()
        
        # Create service with mock providers
        service = EmailService(providers=[provider1, provider2])
        
        # Send email
        result = service.send_email(
            recipient_email="test@example.com",
            strategy=self.reset_strategy,
            reset_link="https://example.com/reset"
        )
        
        # First provider should have failed and not sent
        self.assertEqual(len(provider1.sent_emails), 0)
        
        # Second provider should have sent the email
        self.assertEqual(len(provider2.sent_emails), 1)
        if provider2.sent_emails:
            self.assertEqual(provider2.sent_emails[0]["recipient"], "test@example.com")
        
        # Result should be True
        self.assertTrue(result)
    
    def test_email_service_all_providers_fail(self):
        """Test email service raises exception when all providers fail"""
        # Create providers - both will fail
        provider1 = MockEmailProvider(should_fail=True)
        provider2 = MockEmailProvider(should_fail=True)
        
        # Create service with mock providers
        service = EmailService(providers=[provider1, provider2])
        
        # Send email - should raise exception
        with self.assertRaises(RuntimeError):
            service.send_email(
                recipient_email="test@example.com",
                strategy=self.reset_strategy,
                reset_link="https://example.com/reset"
            )
    
    @patch('authentication.email_services.BrevoEmailProvider.send_email')
    @patch('authentication.email_services.DjangoEmailProvider.send_email')
    def test_real_providers_fallback(self, mock_django_send, mock_brevo_send):
        """Test fallback between real providers"""
        # Make Brevo service fail
        mock_brevo_send.side_effect = Exception("Brevo API error")
        
        # Django service succeeds
        mock_django_send.return_value = True
        
        # Create service with default providers
        service = EmailService()
        
        # Send email
        result = service.send_email(
            recipient_email="test@example.com",
            strategy=self.reset_strategy,
            reset_link="https://example.com/reset"
        )
        
        # Verify both were called in the right order
        mock_brevo_send.assert_called_once()
        mock_django_send.assert_called_once()
        
        # Verify final result
        self.assertTrue(result)
    
    def test_brevo_provider(self):
        """Test Brevo provider specifics"""
        # Create mock for Configuration
        mock_config = MagicMock()
        mock_config_instance = MagicMock()
        # Initialize api_key as a dictionary
        mock_config_instance.api_key = {}
        mock_config.return_value = mock_config_instance
        
        # Rest of the test remains the same
        mock_api_client = MagicMock()
        mock_api = MagicMock()
        mock_api_instance = MagicMock()
        mock_api.return_value = mock_api_instance
        
        with patch('authentication.email_services.sib_api_v3_sdk.Configuration', mock_config):
            with patch('authentication.email_services.ApiClient', mock_api_client):
                with patch('authentication.email_services.TransactionalEmailsApi', mock_api):
                    provider = BrevoEmailProvider(api_key="test-key")
                    provider.send_email(
                        recipient_email="test@example.com",
                        subject="Test Subject",
                        template_name="test_template.html",
                        context={"key": "value"}
                    )
                    
                    # Verify API key was set
                    self.assertEqual(mock_config_instance.api_key, {'api-key': 'test-key'})
    
    def test_django_provider(self):
        """Test Django provider specifics"""
        with patch('authentication.email_services.render_to_string') as mock_render:
            with patch('authentication.email_services.EmailMultiAlternatives.send') as mock_send:
                # Setup mock to render HTML
                mock_render.return_value = "<html>Test Email</html>"
                
                provider = DjangoEmailProvider(from_email="test@example.com")
                provider.send_email(
                    recipient_email="recipient@example.com",
                    subject="Test Subject",
                    template_name="test_template.html",
                    context={"reset_link": "https://example.com/reset"}
                )
                
                # Verify template rendering
                mock_render.assert_called_with("test_template.html", {"reset_link": "https://example.com/reset"})
                
                # Verify email sending
                mock_send.assert_called_once()
    
    def test_missing_template_handled_properly(self):
        """Test that missing template is properly detected and reported"""
        with patch('authentication.email_services.render_to_string') as mock_render:
            mock_render.side_effect = TemplateDoesNotExist("nonexistent_template.html")
            
            provider = DjangoEmailProvider()
            
            with self.assertRaises(FileNotFoundError):
                provider.send_email(
                    recipient_email="test@example.com",
                    subject="Test Subject",
                    template_name="nonexistent_template.html",
                    context={}
                )