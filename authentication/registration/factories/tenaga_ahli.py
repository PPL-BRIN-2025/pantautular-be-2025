from ..base import AbstractRegistrationFactory
from ..registry import register_factory


@register_factory
class TenagaAhliFactory(AbstractRegistrationFactory):
    base_role_name = "TENAGA_AHLI"
    initial_permission_names = ("submit_report", "view_dashboard")
