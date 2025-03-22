from django.db.models import Q
from .strategy import FilterStrategy

class AlertnessFilter(FilterStrategy):
    @property
    def field_name(self) -> str:
        return 'level_of_alertness'

    def build_query(self, value: str) -> Q:
        return Q(disease__level_of_alertness=value) 