from abc import ABC, abstractmethod
import os

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from sib_api_v3_sdk import TransactionalEmailsApi, ApiClient, SendSmtpEmail

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist


class EmailService(ABC):
    @abstractmethod
    def send_password_reset_email(self, recipient_email, reset_link):
        """Send an email with the reset link."""
        pass

class BrevoEmailService(EmailService):
    """Brevo-specific email service implementation"""

    def __init__(self, api_key=None, sender_name="PPL BRIN", sender_email="pplbrin02@gmail.com"):
        self.api_key = api_key or os.getenv("BREVO_API_KEY")
        self.sender = {"name": sender_name, "email": sender_email}

    def send_password_reset_email(self, recipient_email, reset_link, template_id=1):
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = self.api_key
        api_instance = TransactionalEmailsApi(ApiClient(configuration))

        recipients = [{"email": recipient_email}]
        params = {"reset_link": reset_link}

        send_smtp_email = SendSmtpEmail(
            to=recipients,
            sender=self.sender,
            template_id=template_id,
            params=params
        )

        try:
            return api_instance.send_transac_email(send_smtp_email)
        except ApiException as e:
            print(f"Exception when calling TransactionalEmailsApi: {e}")
            raise

class DjangoEmailService(EmailService):
    """Django's built-in email service implementation"""
    def send_password_reset_email(self, recipient_email, reset_link):
        subject = "Password Reset Request"
        from_email = f"PantauTular <{os.getenv('EMAIL_HOST_USER')}>"
        to = [recipient_email]

        try:
            html_content = render_to_string("email_reset_password.html", {
                "reset_link": reset_link,
            })
        except TemplateDoesNotExist:
            raise FileNotFoundError("The template 'email_reset_password.html' does not exist. Please ensure it is available.")
        
        msg = EmailMultiAlternatives(subject, "Please use a HTML-compatible email client", from_email, to)
        msg.attach_alternative(html_content, "text/html")
        try:
            msg.send()
        except Exception as e:
            print(f"Failed to send email: {e}")
            raise