import re
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from pt_backend.models import User
from django.contrib.auth.hashers import make_password, check_password
from .repository import UserRepository
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from authentication.email_services import EmailChainFactory

import os

class UserFinderService:
    def __init__(self, user_repository):
        self.user_repository = user_repository
    
    def find_user_by_email(self, email):
        """Find user by email"""
        return self.user_repository.get_user_by_email(email)

    def find_user_by_id(self, user_id):
        """Find user by ID"""
        return self.user_repository.get_user_by_id(user_id)

class PasswordTokenService:
    def __init__(self, user_repository):
        self.user_repository = user_repository
    
    def generate_password_reset_token(self, user):
        """Generate a password reset token for the user"""
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return uid, token

    def get_user_from_uidb64(self, uidb64):
        """Decode uidb64 and retrieve the user"""
        if uidb64 is None:
            return None
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = self.user_repository.get_user_by_id(uid)
            return user
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None

    def validate_token(self, user, token):
        """Validate if the token is valid for the given user"""
        if not user or not token:
            return False
        return default_token_generator.check_token(user, token)

class ResetLinkService:
    def __init__(self, reset_url_base=None):
        self.reset_url_base = reset_url_base or os.getenv(
            'PROD_PASSWORD_RESET_URL') or os.getenv(
            'DEV_PASSWORD_RESET_URL')
        if not self.reset_url_base:
            print("Warning: Password reset base URL is not configured.")
    
    def create_password_reset_link(self, uid, token):
        """Create a password reset link"""
        if not self.reset_url_base:
            print("Error: Reset URL base is not set.")
            return None
        return f"{self.reset_url_base}/{uid}/{token}"

class PasswordResetService:
    def __init__(self, user_finder, password_token_service, reset_link_service, email_chain_factory=None):
        self.user_finder = user_finder
        self.password_token_service = password_token_service
        self.reset_link_service = reset_link_service

        factory = email_chain_factory or EmailChainFactory()
        self.email_chain = factory.create_email_chain(["brevo", "django"])
    
    def initiate_password_reset(self, email):
        """
        Orchestrates the process of sending a password reset email.
        Returns True if the email was successfully dispatched by a handler, False otherwise.
        """
        user = self.user_finder.find_user_by_email(email)
        if not user:
            print(f"Password reset requested for non-existent email: {email}")
            return True
        
        try:
            uid, token = self.password_token_service.generate_password_reset_token(user)
            reset_link = self.reset_link_service.create_password_reset_link(uid, token)
            if not reset_link:
                print(f"Failed to create password reset link for user: {user.email}. Check base URL config.")
                return False
            
            # Delegate email sending to the chain
            # The chain's handle method returns True if handled, raises error if not.
            # Wrap in try-except to control the return value.
            try:
                self.email_chain.handle(email, reset_link)
                print(f"Password reset email sent to {email}.")
                return True
            except RuntimeError as e:
                print(f"Email chain failed for {email}: {e}")
                return False
            except Exception as e:
                print(f"Unexpected error in email chain for {email}: {e}")
                return False
            
        except Exception as e:
            print(f"Error generating password reset token for {email}: {e}")
            return False

    def verify_reset_attempt(self, uidb64, token):
        """
        Verify token and uid from password reset link.
        Returns the User object if valid, None otherwise.
        """
        user = self.password_token_service.get_user_from_uidb64(uidb64)
        if not user:
            print(f"Invalid UID: {uidb64}")
            return None
        
        if self.password_token_service.validate_token(user, token):
            print(f"Token is valid for user: {user.email}")
            return user
        else:
            print(f"Invalid token for user: {user.email} or token expired.")
            return None

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

    def update_user_password(self, user, current_password: str, new_password: str) -> dict:
        """Update password pengguna yang sudah login"""
        if not self.repository.verify_password(user, current_password):
            return {"success": False, "error": "Current password is incorrect"}
            
        user.password = make_password(new_password)
        self.repository.save_user(user)
        return {"success": True, "message": "Password successfully updated"}

class PasswordValidationService:
    @staticmethod
    def validate_password_match(password, password_confirm):
        """Validate that password and confirmation match."""
        return password == password_confirm
    
    @staticmethod
    def validate_password_strength(password):
        """
        Validate password strength requirements.
        Returns (bool, str): (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "Password harus minimal 8 karakter"
            
        if not re.search(r'[A-Z]', password):
            return False, "Password harus mengandung minimal 1 huruf besar"
            
        if not re.search(r'[a-z]', password):
            return False, "Password harus mengandung minimal 1 huruf kecil"
            
        if not re.search(r'\d', password):
            return False, "Password harus mengandung minimal 1 angka"
            
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>/?]', password):
            return False, "Password harus mengandung minimal 1 karakter spesial"
            
        return True, ""

class AuthService:
    def __init__(self, user_repository):
        self.user_repository = user_repository
    
    def _get_lockout_cache_key(self, email):
        """Generate a unique cache key for tracking login attempts"""
        return f"login_attempts_{email.lower()}"
    
    def check_account_locked(self, email):
        """
        Check if account is locked due to too many failed attempts
        Returns tuple (is_locked, remaining_time_in_seconds or None)
        """
        cache_key = self._get_lockout_cache_key(email)
        lockout_data = cache.get(cache_key, {})
        
        # If no lockout data, account is not locked
        if not lockout_data:
            return False, None
            
        # Check if attempts exceeded and lock is still active
        attempts = lockout_data.get('attempts', 0)
        locked_until = lockout_data.get('locked_until')
        
        max_attempts = getattr(settings, 'ACCOUNT_LOCKOUT', {}).get('MAX_FAILED_ATTEMPTS', 5)
        
        if attempts >= max_attempts and locked_until:
            now = timezone.now().timestamp()
            if locked_until > now:
                # Account is locked, calculate remaining time
                remaining = int(locked_until - now)
                return True, remaining
                
        return False, None
    
    def increment_failed_attempts(self, email):
        """
        Increment the number of failed attempts for an email
        Lock the account if max attempts reached
        """
        cache_key = self._get_lockout_cache_key(email)
        lockout_data = cache.get(cache_key, {'attempts': 0})
        
        # Increment attempts
        lockout_data['attempts'] = lockout_data.get('attempts', 0) + 1
        
        max_attempts = getattr(settings, 'ACCOUNT_LOCKOUT', {}).get('MAX_FAILED_ATTEMPTS', 5)
        lockout_duration = getattr(settings, 'ACCOUNT_LOCKOUT', {}).get('LOCKOUT_DURATION', 60 * 15)
        
        # If max attempts reached, set lockout time
        if lockout_data['attempts'] >= max_attempts:
            lockout_data['locked_until'] = timezone.now().timestamp() + lockout_duration
            # Cache for the lockout duration
            cache.set(cache_key, lockout_data, lockout_duration)
        else:
            # Cache for a longer time to track attempts across sessions
            cache.set(cache_key, lockout_data, 24 * 60 * 60)  # 24 hours
    
    def reset_failed_attempts(self, email):
        """Reset failed attempts counter after successful login"""
        cache_key = self._get_lockout_cache_key(email)
        cache.delete(cache_key)
    
    def login(self, email, password):
        """
        Authenticate user and generate tokens
        
        Returns:
            dict: JWT tokens if authentication successful
            None: If authentication fails
            dict with 'locked' key: If account is locked
        """
        # Check if account is locked
        is_locked, remaining_time = self.check_account_locked(email)
        if is_locked:
            minutes = remaining_time // 60
            seconds = remaining_time % 60
            time_msg = f"{minutes} minutes and {seconds} seconds" if minutes else f"{seconds} seconds"
            return {
                'locked': True,
                'message': f"Account is locked due to too many failed attempts. Try again in {time_msg}."
            }
            
        # Get user by email
        user = self.user_repository.get_user_by_email(email)
        
        if not user:
            # Increment failed attempts even for non-existent emails to prevent enumeration
            self.increment_failed_attempts(email)
            return None
        
        # Check password
        if not check_password(password, user.password):
            self.increment_failed_attempts(email)
            return None
        
        # Successful login, reset failed attempts
        self.reset_failed_attempts(email)
        
        # Generate token with user data in payload
        refresh = RefreshToken.for_user(user)
        
        # Menambahkan data user ke payload token
        refresh['name'] = user.name
        refresh['email'] = user.email
        refresh['role'] = user.role
        refresh['user_id'] = user.id
        
        # Hanya mengembalikan token
        return {
            "access_token": str(refresh.access_token)
        }