from authentication.email_services import EmailSender, EmailChainHandler

class MockEmailService(EmailSender, EmailChainHandler):
    def __init__(self, should_fail=False):
        super().__init__() 
        self.sent_emails = []
        self.should_fail = should_fail
    
    def send_password_reset_email(self, recipient_email, reset_link, template_id=None):
        if self.should_fail:
            raise RuntimeError("Mock service failure")
            
        self.sent_emails.append({
            "recipient": recipient_email,
            "reset_link": reset_link,
            "template_id": template_id
        })
        return True