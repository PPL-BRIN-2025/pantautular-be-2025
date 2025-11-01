from datetime import datetime
from typing import Dict, Optional, Tuple

from django.db.models import Q, QuerySet
from pt_backend.models import Case
from .disease_filter import DiseaseFilter
from .location_filter import LocationFilter
from .alertness_filter import AlertnessFilter
from .portal_filter import PortalFilter
from .date_range_filter import DateRangeFilter

class CaseFilterService:
    def __init__(self):
        self.date_range_filter = DateRangeFilter()
        self.filters = [
            DiseaseFilter(),
            LocationFilter(),
            AlertnessFilter(),
            PortalFilter(),
            self.date_range_filter,
        ]

    def filter_cases(self, data: Dict) -> QuerySet:
        # Build base query with optimizations
        base_query = (
            Case.objects
            .select_related('location', 'disease')  # Optimize foreign key lookups
            .prefetch_related('news_set')  # Optimize reverse relation lookups
        )

        # Build filter query
        query = Q()
        for filter_strategy in self.filters:
            if q_object := filter_strategy.apply(data):
                query &= q_object

        # Apply filters and return optimized query
        return (
            base_query
            .filter(query)
            .values('id', 'location__longitude', 'location__latitude', 'city', 'location__province', 'severity')
            .distinct()
        )

    @staticmethod
    def time_window(
        data: Dict,
        *,
        field: str,
        start_key: str = DateRangeFilter.DEFAULT_START_KEY,
        end_key: str = DateRangeFilter.DEFAULT_END_KEY,
        timezone=None,
        null_guard_field: Optional[str] = None,
        period_key: str = DateRangeFilter.DEFAULT_PERIOD_KEY,
        tz_key: str = DateRangeFilter.DEFAULT_TZ_KEY,
        now: Optional[datetime] = None,
    ) -> Optional[Q]:
        return DateRangeFilter.build_time_window(
            field=field,
            data=data,
            start_key=start_key,
            end_key=end_key,
            timezone=timezone,
            null_guard_field=null_guard_field,
            period_key=period_key,
            tz_key=tz_key,
            now=now,
        )

    @staticmethod
    def resolve_time_window(
        data: Dict,
        *,
        start_key: str = DateRangeFilter.DEFAULT_START_KEY,
        end_key: str = DateRangeFilter.DEFAULT_END_KEY,
        period_key: str = DateRangeFilter.DEFAULT_PERIOD_KEY,
        tz_key: str = DateRangeFilter.DEFAULT_TZ_KEY,
        timezone=None,
        now: Optional[datetime] = None,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        return DateRangeFilter.resolve_time_window(
            data,
            start_key=start_key,
            end_key=end_key,
            period_key=period_key,
            tz_key=tz_key,
            timezone=timezone,
            now=now,
        )
