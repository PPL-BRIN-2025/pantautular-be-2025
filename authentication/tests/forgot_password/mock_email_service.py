from authentication.email_services import EmailService

class MockEmailService(EmailService):
    """Mock email service for testing"""
    
    def __init__(self):
        self.sent_emails = []
    
    def send_password_reset_email(self, recipient_email, reset_link, template_id=None):
        """Record emails instead of sending them"""
        self.sent_emails.append({
            "recipient": recipient_email,
            "reset_link": reset_link,
            "template_id": template_id
        })
        return True