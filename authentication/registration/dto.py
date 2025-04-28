from dataclasses import dataclass
from typing import List
from pt_backend.models import User, Role, Permission


@dataclass(frozen=True)
class RegisteredUserDTO:
    user: User
    role: Role
    permissions: List[Permission]

    def __str__(self) -> str:
        return f"{self.user} ({self.role.name})"
