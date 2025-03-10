from django.db.models import Q
from .strategy import FilterStrategy

class PortalFilter(FilterStrategy):
    @property
    def field_name(self) -> str:
        return 'portals'

    def build_query(self, value: list) -> Q:
        return Q(news__portal__in=value) 