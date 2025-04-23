from __future__ import annotations
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from ..registration import get_factory
from .dto import RegisteredUserDTO
from pt_backend.models import User  


class RegistrationError(Exception):
    """Raised when the registration flow cannot complete."""


class RegistrationService:

    @classmethod
    @transaction.atomic
    def register_user(
        cls,
        *,
        role_name: str,
        name: str,
        email: str,
        password: str,
        **extra_user_fields,
    ) -> RegisteredUserDTO:
        try:
            cls._ensure_email_unused(email)
            validate_password(password)

            factory = get_factory(role_name)
            dto = factory.register(
                name=name,
                email=email,
                raw_password=password,
                **extra_user_fields,
            )

            cls._send_welcome_email(dto)

            return dto

        except (ValidationError, Exception) as exc:
            raise RegistrationError(str(exc)) from exc

    @staticmethod
    def _ensure_email_unused(email: str) -> None:
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this e-mail already exists.")
        
    @staticmethod
    def _send_welcome_email(dto: RegisteredUserDTO) -> None:
        """For further development process"""
        pass
