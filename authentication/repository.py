from pt_backend.models import User
from django.contrib.auth.hashers import check_password

class UserRepository:
    @staticmethod
    def get_user_by_email(email: str) -> User: # NOSONAR
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None

    @staticmethod
    def save_user(user: User) -> None:
        user.save()

    @staticmethod
    def verify_password(user: User, password: str) -> bool:
        """Verifikasi password pengguna"""
        return check_password(password, user.password)
