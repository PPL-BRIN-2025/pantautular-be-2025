from abc import ABC, abstractmethod
import os

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from sib_api_v3_sdk import TransactionalEmailsApi, ApiClient, SendSmtpEmail

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