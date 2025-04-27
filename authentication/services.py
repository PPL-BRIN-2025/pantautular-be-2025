from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.hashers import check_password
from rest_framework_simplejwt.tokens import RefreshToken

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