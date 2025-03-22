from django.db.models import Q
from .strategy import FilterStrategy

class LocationFilter(FilterStrategy):
    @property
    def field_name(self) -> str:
        return 'locations'

    def build_query(self, value: list) -> Q:
        return Q(location__name__in=value) 