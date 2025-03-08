from django.db.models import Q
from .strategy import FilterStrategy
from typing import Dict

class DiseaseFilter(FilterStrategy):
    @property
    def field_name(self) -> str:
        return 'diseases'

    def build_query(self, value: list) -> Q:
        return Q(disease__name__in=value)

class LocationFilter(FilterStrategy):
    @property
    def field_name(self) -> str:
        return 'locations'

    def build_query(self, value: list) -> Q:
        return Q(location__name__in=value)

class AlertnessFilter(FilterStrategy):
    @property
    def field_name(self) -> str:
        return 'level_of_alertness'

    def build_query(self, value: str) -> Q:
        return Q(disease__level_of_alertness=value)

class PortalFilter(FilterStrategy):
    @property
    def field_name(self) -> str:
        return 'portals'

    def build_query(self, value: list) -> Q:
        return Q(news__portal__in=value)

class DateRangeFilter(FilterStrategy):
    @property
    def field_name(self) -> str:
        return 'date_range'

    def should_apply(self, data: Dict) -> bool:
        date_range = data.get(self.field_name, {})
        return bool(date_range.get('start_date') and date_range.get('end_date'))

    def build_query(self, value: Dict) -> Q:
        return Q(date_published__range=[value['start_date'], value['end_date']]) 