from django.db.models import Q
from .strategy import FilterStrategy

class LocationFilter(FilterStrategy):
    @property
    def field_name(self):
        return 'locations'

    def build_query(self, values):
        return Q(location__city__in=values) | Q(location__province__in=values) 