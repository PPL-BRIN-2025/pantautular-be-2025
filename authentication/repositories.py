class UserRepository:
    def get_user_by_email(self, email):
        """Retrieve user by email (case insensitive)"""
        from pt_backend.models import User
        return User.objects.filter(email__iexact=email).first()