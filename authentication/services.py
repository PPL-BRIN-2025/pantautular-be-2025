from django.contrib.auth.hashers import check_password
from rest_framework_simplejwt.tokens import RefreshToken

class AuthService:
    def __init__(self, user_repository):
        self.user_repository = user_repository
        
    def login(self, email, password):
        """
        Authenticate user and generate tokens
        
        Returns:
            dict: JWT tokens if authentication successful
            None: If authentication fails
        """
        # Get user by email
        user = self.user_repository.get_user_by_email(email)
        
        if not user:
            return None
        
        # Check password
        if not check_password(password, user.password):
            return None
        
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