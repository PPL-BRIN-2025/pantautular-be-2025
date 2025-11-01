from collections.abc import Mapping
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union

from django.db.models import Q, QuerySet
from django.http import QueryDict
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

    @classmethod
    def parse_time_params(
        cls,
        params: Union[Mapping[str, Any], QueryDict, Dict[str, Any]],
        *,
        start_key: str = DateRangeFilter.DEFAULT_START_KEY,
        end_key: str = DateRangeFilter.DEFAULT_END_KEY,
        period_key: str = DateRangeFilter.DEFAULT_PERIOD_KEY,
        tz_key: str = DateRangeFilter.DEFAULT_TZ_KEY,
        timezone=None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        raw_values, start_dt, end_dt = cls._resolve_from_params(
            params,
            start_key=start_key,
            end_key=end_key,
            period_key=period_key,
            tz_key=tz_key,
            timezone=timezone,
            now=now,
        )

        payload: Dict[str, Any] = {}
        if start_dt:
            payload[start_key] = start_dt.isoformat()
        if end_dt:
            payload[end_key] = end_dt.isoformat()

        if raw_values.get(tz_key):
            payload[tz_key] = raw_values[tz_key]
        if raw_values.get(period_key):
            payload[period_key] = raw_values[period_key]

        return payload

    @classmethod
    def parse_time_range(
        cls,
        params: Union[Mapping[str, Any], QueryDict, Dict[str, Any]],
        *,
        start_key: str = DateRangeFilter.DEFAULT_START_KEY,
        end_key: str = DateRangeFilter.DEFAULT_END_KEY,
        period_key: str = DateRangeFilter.DEFAULT_PERIOD_KEY,
        tz_key: str = DateRangeFilter.DEFAULT_TZ_KEY,
        timezone=None,
        now: Optional[datetime] = None,
        return_type: str = "dict",
    ) -> Optional[Union[Dict[str, Optional[datetime]], Tuple[Optional[datetime], Optional[datetime]]]]:
        _, start_dt, end_dt = cls._resolve_from_params(
            params,
            start_key=start_key,
            end_key=end_key,
            period_key=period_key,
            tz_key=tz_key,
            timezone=timezone,
            now=now,
        )

        if not start_dt and not end_dt:
            return None

        if return_type == "tuple":
            return start_dt, end_dt

        return {
            "start": start_dt,
            "end": end_dt,
        }

    @classmethod
    def _resolve_from_params(
        cls,
        params: Union[Mapping[str, Any], QueryDict, Dict[str, Any]],
        *,
        start_key: str,
        end_key: str,
        period_key: str,
        tz_key: str,
        timezone,
        now: Optional[datetime],
    ) -> Tuple[Dict[str, Any], Optional[datetime], Optional[datetime]]:
        raw_values = {
            start_key: cls._extract_param_value(params, start_key),
            end_key: cls._extract_param_value(params, end_key),
            period_key: cls._extract_param_value(params, period_key),
            tz_key: cls._extract_param_value(params, tz_key),
        }

        start_dt, end_dt = cls.resolve_time_window(
            raw_values,
            start_key=start_key,
            end_key=end_key,
            period_key=period_key,
            tz_key=tz_key,
            timezone=timezone,
            now=now,
        )

        return raw_values, start_dt, end_dt

    @staticmethod
    def _extract_param_value(
        params: Union[Mapping[str, Any], QueryDict, Dict[str, Any]],
        key: str,
    ) -> Any:
        if not params or key is None:
            return None

        if isinstance(params, QueryDict):
            values = params.getlist(key)
            return CaseFilterService._first_non_empty(values)

        if hasattr(params, "get"):
            value = params.get(key)
        else:
            value = getattr(params, key, None)

        return CaseFilterService._first_non_empty(value)

    @staticmethod
    def _first_non_empty(value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            for item in value:
                if item not in (None, ""):
                    return item
            return None
        return value
