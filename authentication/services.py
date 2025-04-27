from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from pt_backend.models import User
from django.contrib.auth.hashers import make_password
from .repository import UserRepository

import os
from authentication.email_services import BrevoEmailService

class PasswordResetService:
    def __init__(self, reset_url_base=None, email_service=None):
        self.reset_url_base = reset_url_base or os.getenv(
            'PROD_PASSWORD_RESET_URL') or os.getenv(
            'DEV_PASSWORD_RESET_URL')
        
        self.email_service = email_service or BrevoEmailService()
    
    def find_user_by_email(self, email):
        return User.objects.get(email=email) if User.objects.filter(email=email).exists() else None
    
    def generate_password_reset_token(self, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return uid, token

    def create_password_reset_link(self, uid, token):
        return f"{self.reset_url_base}?uid={uid}&token={token}"
    
    def process_reset_request(self, email):
        user = self.find_user_by_email(email)
        uid, token = self.generate_password_reset_token(user)
        reset_link = self.create_password_reset_link(uid, token)
        self.email_service.send_password_reset_email(email, reset_link)
        return True
    
    def get_user_from_uidb64(self, uidb64):
        """Decode uidb64 and retrieve the user"""
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
            return user
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None
    
    def validate_token(self, user, token):
        """Validate if the token is valid for the given user"""
        if not user:
            return False
        return default_token_generator.check_token(user, token)
    
class ChangePasswordService:
    def __init__(self, repository: UserRepository = UserRepository()):
        self.repository = repository

    def change_password(self, email: str, new_password: str) -> bool:
        user = self.repository.get_user_by_email(email)
        if not user:
            return False

        user.password = make_password(new_password)
        self.repository.save_user(user)
        return True