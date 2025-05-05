from abc import ABC, abstractmethod
import os

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from sib_api_v3_sdk import TransactionalEmailsApi, ApiClient, SendSmtpEmail

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist

class ChainHandler(ABC):
    """Interface for classes that can be part of a responsibility chain."""
    def __init__(self):
        self._next_handler = None

    def set_next(self, handler):
        self._next_handler = handler
        return handler

    def handle(self, recipient_email, reset_link):
        """Template method that defines the handling algorithm"""
        try:
            # Let subclasses decide if they can handle it
            if self.can_handle(recipient_email, reset_link):
                return True
            else:
                # Forward to next handler if available
                if self._next_handler:
                    return self._next_handler.handle(recipient_email, reset_link)
                # No handler could process the request
                raise RuntimeError("No handler was able to process the request")
        except Exception as e:
            print(f"{self.__class__.__name__} failed: {e}")
            if self._next_handler:
                return self._next_handler.handle(recipient_email, reset_link)
            raise

    @abstractmethod
    def can_handle(self, recipient_email, reset_link):
        """Subclasses should implement this to check if they can handle the request."""
        pass

class EmailSender(ABC):
    """Interface for classes that send can send password reset emails."""
    @abstractmethod
    def send_password_reset_email(self, recipient_email, reset_link):
        pass

class EmailChainHandler(ChainHandler):
    """Base class for email-sending handlers"""
    
    def can_handle(self, recipient_email, reset_link):
        """Attempt to send email and return success/failure"""
        try:
            self.send_password_reset_email(recipient_email, reset_link)
            return True
        except Exception as e:
            print(f"Handler {self.__class__.__name__} could not process request: {e}")
            return False
    
class BrevoEmailService(EmailSender, EmailChainHandler):
    """Brevo-specific email service implementation"""

    def __init__(self, api_key=None, sender_name="PPL BRIN", sender_email="pplbrin02@gmail.com"):
        super().__init__()
        self.api_key = api_key or os.getenv("BREVO_API_KEY")
        self.sender = {"name": sender_name, "email": sender_email}
        
    def send_password_reset_email(self, recipient_email, reset_link):
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = self.api_key
        api_instance = TransactionalEmailsApi(ApiClient(configuration))

        recipients = [{"email": recipient_email}]
        params = {"reset_link": reset_link}

        send_smtp_email = SendSmtpEmail(
            to=recipients,
            sender=self.sender,
            template_id=1,
            params=params
        )

        try:
            return api_instance.send_transac_email(send_smtp_email)
        except ApiException as e:
            print(f"Exception when calling TransactionalEmailsApi: {e}")
            raise

class DjangoEmailService(EmailSender, EmailChainHandler):
    def __init__(self, from_email=None, subject="Password Reset Request", template_name="email_reset_password.html"):
        super().__init__()
        self.from_email = from_email or f"PantauTular <{os.getenv('EMAIL_HOST_USER')}>"
        self.subject = subject
        self.template_name = template_name

    """Django's built-in email service implementation"""
    def send_password_reset_email(self, recipient_email, reset_link):
        subject = self.subject
        from_email = self.from_email
        to = [recipient_email]

        try:
            html_content = render_to_string(self.template_name, {
                "reset_link": reset_link,
            })
        except TemplateDoesNotExist:
            raise FileNotFoundError("The template 'email_reset_password.html' does not exist. Please ensure it is available.")
        
        text_content = f"Reset your password by visiting this link: {reset_link}"
        msg = EmailMultiAlternatives(subject, text_content, from_email, to)
        msg.attach_alternative(html_content, "text/html")
        try:
            msg.send()
        except Exception as e:
            print(f"Failed to send email: {e}")
            raise

def create_default_email_chain():
    """Create a default email chain with Brevo and Django services"""
    brevo = BrevoEmailService()
    django = DjangoEmailService()
    brevo.set_next(django)
    return brevo