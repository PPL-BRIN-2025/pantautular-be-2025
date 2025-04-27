from pt_backend.models import User
from django.core.exceptions import ObjectDoesNotExist

class UserRepository:
    @staticmethod
    def get_user_by_email(email: str) -> User: # NOSONAR
        try:
            return User.objects.get(email=email)
        except ObjectDoesNotExist:
            return None # NOSONAR

    @staticmethod
    def save_user(user: User) -> None:
        user.save()
