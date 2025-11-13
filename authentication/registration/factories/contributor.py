from ..base import AbstractRegistrationFactory
from ..registry import register_factory


@register_factory
class ContributorFactory(AbstractRegistrationFactory):
    base_role_name = "CONTRIBUTOR"
    initial_permission_names = ("submit_report", "view_dashboard")
