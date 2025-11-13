"""Filter strategies for expert dashboard case queries.

Applying the Strategy pattern keeps each filter independent and lets the
download workflow opt in/out of specific filters without touching the callers.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Sequence

from django.db.models import QuerySet
from django.utils import timezone


class CaseQueryFilter:
    """Simple Strategy interface used by the expert dashboard."""

    def apply(self, queryset: QuerySet, filters: dict) -> QuerySet:
        raise NotImplementedError


class CaseDiseaseFilter(CaseQueryFilter):
    def apply(self, queryset: QuerySet, filters: dict) -> QuerySet:
        diseases = filters.get("diseases")
        if diseases:
            return queryset.filter(disease__name__in=diseases)
        return queryset


class CasePortalFilter(CaseQueryFilter):
    def apply(self, queryset: QuerySet, filters: dict) -> QuerySet:
        portals = filters.get("portals")
        if portals:
            return queryset.filter(news__portal__in=portals)
        return queryset


class CaseAlertnessFilter(CaseQueryFilter):
    def apply(self, queryset: QuerySet, filters: dict) -> QuerySet:
        level = filters.get("level_of_alertness")
        if level is not None:
            return queryset.filter(disease__level_of_alertness=level)
        return queryset


def _location_filters(filters: dict) -> dict:
    return filters.get("locations") or {}


class CaseProvinceFilter(CaseQueryFilter):
    def apply(self, queryset: QuerySet, filters: dict) -> QuerySet:
        provinces = _location_filters(filters).get("provinces")
        if provinces:
            return queryset.filter(location__province__in=provinces)
        return queryset


class CaseCityFilter(CaseQueryFilter):
    def apply(self, queryset: QuerySet, filters: dict) -> QuerySet:
        cities = _location_filters(filters).get("cities")
        if cities:
            return queryset.filter(location__city__in=cities)
        return queryset


class CaseDateRangeFilter(CaseQueryFilter):
    def apply(self, queryset: QuerySet, filters: dict) -> QuerySet:
        start = filters.get("start_date")
        end = filters.get("end_date")
        tz = timezone.get_current_timezone()

        if start:
            start_bound = timezone.make_aware(datetime.combine(start, time.min), timezone=tz)
            queryset = queryset.filter(news__date_published__gte=start_bound)

        if end:
            end_bound = timezone.make_aware(datetime.combine(end, time.max), timezone=tz)
            queryset = queryset.filter(news__date_published__lte=end_bound)

        return queryset


class ExpertCaseFilterSet:
    """Aggregates the individual filters to comply with Open/Closed."""

    def __init__(self, strategies: Sequence[CaseQueryFilter] | None = None):
        self.strategies: Sequence[CaseQueryFilter] = tuple(strategies or DEFAULT_CASE_FILTERS)

    def apply(self, filters: dict, queryset: QuerySet) -> QuerySet:
        applied_filters = filters or {}
        qs = queryset
        for strategy in self.strategies:
            qs = strategy.apply(qs, applied_filters)
        return qs.distinct()


DEFAULT_CASE_FILTERS: Sequence[CaseQueryFilter] = (
    CaseDiseaseFilter(),
    CasePortalFilter(),
    CaseAlertnessFilter(),
    CaseProvinceFilter(),
    CaseCityFilter(),
    CaseDateRangeFilter(),
)


__all__ = [
    "CaseQueryFilter",
    "CaseDiseaseFilter",
    "CasePortalFilter",
    "CaseAlertnessFilter",
    "CaseProvinceFilter",
    "CaseCityFilter",
    "CaseDateRangeFilter",
    "ExpertCaseFilterSet",
    "DEFAULT_CASE_FILTERS",
]
