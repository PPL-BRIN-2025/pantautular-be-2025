# from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from pt_backend.models import User

class PasswordResetService:
    def __init__(self, reset_url_base="http://localhost:3000/authentication/reset-password"):
        self.reset_url_base = reset_url_base
    
    @staticmethod
    def get_user_model():
        return User
    
    def find_user_by_email(self, email):
        user_model = self.get_user_model()
        return user_model.objects.get(email=email) if user_model.objects.filter(email=email).exists() else None
    
    def generate_password_reset_token(self, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return uid, token

    def create_password_reset_link(self, uid, token):
        return f"{self.reset_url_base}/{uid}/{token}"
    
    def send_password_reset_email(self, email, reset_link):
        send_mail(
            subject="Reset Password Akunmu",
            message=f"Klik link berikut untuk mereset password akunmu: {reset_link}",
            from_email="no-reply@gmail.com",
            recipient_list=[email],
            fail_silently=False,
        )
    
    def process_reset_request(self, email):
        user = self.find_user_by_email(email)
        uid, token = self.generate_password_reset_token(user)
        reset_link = self.create_password_reset_link(uid, token)
        self.send_password_reset_email(email, reset_link)
        return True