from django.db.models import Q, QuerySet
from typing import Dict
from pt_backend.models import Case
from .filters import (
    DiseaseFilter,
    LocationFilter,
    AlertnessFilter,
    PortalFilter,
    DateRangeFilter
)


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
        query = Q()
        
        for filter_strategy in self.filters:
            if q_object := filter_strategy.apply(data):
                query &= q_object

        return (
            Case.objects
            .filter(query)
            .values('id', 'location__longitude', 'location__latitude', 'city')
            .distinct()
        )