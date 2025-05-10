from abc import ABC, abstractmethod
import os
import logging

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from sib_api_v3_sdk import TransactionalEmailsApi, ApiClient, SendSmtpEmail

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist

logger = logging.getLogger(__name__)

# Strategy Pattern for email content
class EmailContentStrategy(ABC):
    """Strategy interface for different types of email content"""
    
    @abstractmethod
    def get_subject(self):
        """Get the email subject line"""
        pass
    
    @abstractmethod
    def get_template_name(self):
        """Get the template name for this email type"""
        pass
    
    @abstractmethod
    def get_context_data(self, **kwargs):
        """Get the template context data"""
        pass

class PasswordResetEmailStrategy(EmailContentStrategy):
    """Strategy for password reset emails"""
    
    def get_subject(self):
        return "Password Reset Request"
    
    def get_template_name(self):
        return "email_reset_password.html"
    
    def get_context_data(self, **kwargs):
        reset_link = kwargs.get('reset_link')
        if not reset_link:
            raise ValueError("Reset link is required for password reset emails")
        
        return {"reset_link": reset_link}

# Email Provider Interface
class EmailProvider(ABC):
    """Interface for classes that can send emails."""
    
    @abstractmethod
    def send_email(self, recipient_email, subject, template_name, context):
        """Send an email with the given subject, template and context"""
        pass

# Concrete email providers
class BrevoEmailProvider(EmailProvider):
    """Brevo-specific email service implementation"""

    def __init__(self, api_key=None, sender_name="PPL BRIN", sender_email="pplbrin02@gmail.com"):
        self.api_key = api_key or os.getenv("BREVO_API_KEY")
        self.sender = {"name": sender_name, "email": sender_email}
        
    def send_email(self, recipient_email, subject, template_name, context):
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = self.api_key
        api_instance = TransactionalEmailsApi(ApiClient(configuration))

        recipients = [{"email": recipient_email}]
        params = context  # Pass the context as params

        send_smtp_email = SendSmtpEmail(
            to=recipients,
            sender=self.sender,
            template_id=1,
            params=params
        )

        try:
            return api_instance.send_transac_email(send_smtp_email)
        except ApiException as e:
            logger.error(f"Exception when calling TransactionalEmailsApi: {e}")
            raise

class DjangoEmailProvider(EmailProvider):
    """Django's built-in email service implementation"""
    
    def __init__(self, from_email=None):
        self.from_email = from_email or f"PantauTular <{os.getenv('EMAIL_HOST_USER')}>"

    def send_email(self, recipient_email, subject, template_name, context):
        from_email = self.from_email
        to = [recipient_email]

        try:
            html_content = render_to_string(template_name, context)
        except TemplateDoesNotExist:
            raise FileNotFoundError(f"The template '{template_name}' does not exist.")
        
        # Create a simple text version of the email
        text_content = "Please view this email in an HTML-capable client to see the content."
        if "reset_link" in context:
            text_content = f"Reset your password by visiting this link: {context['reset_link']}"
            
        msg = EmailMultiAlternatives(subject, text_content, from_email, to)
        msg.attach_alternative(html_content, "text/html")
        
        try:
            msg.send()
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise

# Email Service with fallback mechanism
class EmailService:
    """Service that manages multiple email providers with fallback capability"""
    
    def __init__(self, providers=None):
        """
        Initialize with a list of email providers
        
        Args:
            providers: List of EmailProvider implementations to try in order
        """
        self.providers = providers or self._get_default_providers()
    
    def send_email(self, recipient_email, strategy, **kwargs):
        """
        Send an email using the given strategy, trying each provider until one succeeds
        
        Args:
            recipient_email: Recipient's email address
            strategy: EmailContentStrategy to use for content preparation
            **kwargs: Additional data needed by the strategy
        """
        subject = strategy.get_subject()
        template_name = strategy.get_template_name()
        context = strategy.get_context_data(**kwargs)
        
        last_error = None
        
        for provider in self.providers:
            try:
                provider.send_email(recipient_email, subject, template_name, context)
                logger.info(f"Email sent successfully using {provider.__class__.__name__}")
                print(f"Email sent successfully using {provider.__class__.__name__}")
                return True
            except Exception as e:
                logger.warning(f"{provider.__class__.__name__} failed to send email: {e}")
                last_error = e
                continue
        
        # If we get here, all providers failed
        logger.error("All email providers failed to send email")
        raise RuntimeError(f"Failed to send email: {str(last_error)}")
    
    @staticmethod
    def _get_default_providers():
        """Get the default list of email providers"""
        return [
            BrevoEmailProvider(),
            DjangoEmailProvider()
        ]