from django.db.models import Q
from .strategy import FilterStrategy
from typing import Dict

class DateRangeFilter(FilterStrategy):
    @property
    def field_name(self) -> str:
        return 'date_range'

    def should_apply(self, data: Dict) -> bool:
        date_range = data.get(self.field_name, {})
        return bool(date_range.get('start_date') and date_range.get('end_date'))

    def build_query(self, value: Dict) -> Q:
        return Q(date_published__range=[value['start_date'], value['end_date']]) 