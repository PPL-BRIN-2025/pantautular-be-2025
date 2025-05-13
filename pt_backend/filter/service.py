from django.db.models import Q, QuerySet
from typing import Dict
from pt_backend.models import Case
from .disease_filter import DiseaseFilter
from .location_filter import LocationFilter
from .alertness_filter import AlertnessFilter
from .portal_filter import PortalFilter
from .date_range_filter import DateRangeFilter

class CaseFilterService:
    def __init__(self):
        self.filters = [
            DiseaseFilter(),
            LocationFilter(),
            AlertnessFilter(),
            PortalFilter(),
            DateRangeFilter()
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
            .values('id', 'location__longitude', 'location__latitude', 'city', 'location__province')
            .distinct()
        )
