from django.db.models import Q
from .strategy import FilterStrategy

class DiseaseFilter(FilterStrategy):
    @property
    def field_name(self) -> str:
        return 'diseases'

    def build_query(self, value: list) -> Q:
        return Q(disease__name__in=value) 