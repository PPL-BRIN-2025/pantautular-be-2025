from __future__ import annotations
from abc import ABC
from typing import Iterable, List

from django.db import transaction
from django.contrib.auth.hashers import make_password

from pt_backend.models import (
    User,
    Role,
    Permission,
    UserRole,
    RolePermission,
)
from .dto import RegisteredUserDTO


class AbstractRegistrationFactory(ABC):
    base_role_name: str
    initial_permission_names: Iterable[str] = ()

    # ---------- public API --------------------------------------------------
    @transaction.atomic
    def register(self, *, name: str, email: str, raw_password: str, **extra) -> RegisteredUserDTO:
        role = self._get_or_create_role()
        perms = self._get_or_create_permissions()

        user = User.objects.create(
            name=name,
            email=email,
            password=make_password(raw_password),
            role=role.name,      # keep legacy CharField filled
            **extra,
        )
        UserRole.objects.create(user=user, role=role)
        for perm in perms:
            RolePermission.objects.get_or_create(role=role, permission=perm)

        return RegisteredUserDTO(user, role, perms)

    # ---------- helpers -----------------------------------------------------
    def _get_or_create_role(self) -> Role:
        return Role.objects.get_or_create(name=self.base_role_name.upper())[0]

    def _get_or_create_permissions(self) -> List[Permission]:
        out: List[Permission] = []
        for name in self.initial_permission_names:
            perm, _ = Permission.objects.get_or_create(
                name=name,
                defaults={"description": name.replace("_", " ").capitalize()},
            )
            out.append(perm)
        return out
