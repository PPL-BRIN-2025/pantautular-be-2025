from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Tuple, Union
from uuid import UUID

from django.db.models import Q, QuerySet
from django.http import QueryDict

from pt_backend.models import Case
from .alertness_filter import AlertnessFilter
from .date_range_filter import DateRangeFilter, TimeWindowError
from .disease_filter import DiseaseFilter
from .location_filter import LocationFilter
from .portal_filter import PortalFilter


class CaseFilterValidationError(ValueError):
    """Uniform error wrapper for HTTP 400 responses."""

    DEFAULT_CODE = "invalid_time_window"

    def __init__(
        self,
        message: str,
        *,
        code: str = DEFAULT_CODE,
        fields: Optional[Dict[str, list]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.fields = fields or {}

    def as_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": str(self),
            }
        }
        if self.fields:
            payload["error"]["fields"] = self.fields
        return payload

    @classmethod
    def from_time_error(cls, error: TimeWindowError) -> "CaseFilterValidationError":
        return cls(str(error), fields=getattr(error, "fields", {}))


class CaseFilterService:
    """Case filter orchestration that depends only on the minimal time-filter interface."""

    def __init__(self, time_filter: Optional[DateRangeFilter] = None):
        self.time_filter = time_filter or DateRangeFilter()
        self.filters = [
            DiseaseFilter(),
            LocationFilter(),
            AlertnessFilter(),
            PortalFilter(),
            self.time_filter,
        ]
        self._time_field = "news__date_published"
        self._time_null_guard = "news"
        self._time_window_cache: "OrderedDict[Tuple[Optional[str], Optional[str]], Optional[Q]]" = OrderedDict()
        self._time_window_cache_size = 32

    def filter_cases(self, data: Mapping[str, Any]) -> QuerySet:
        base_query = (
            Case.objects
            .select_related('location', 'disease')
            .prefetch_related('news_set')
        )

        batch_id = self._extract_batch_id(data)
        if batch_id:
            base_query = base_query.filter(batch_id=batch_id)

        time_window_q = self._get_time_window_q(data)

        query = Q()
        has_query_filters = False
        for filter_strategy in self.filters:
            if filter_strategy is self.time_filter:
                continue
            if q_object := filter_strategy.apply(data):
                query &= q_object
                has_query_filters = True

        if time_window_q is not None:
            base_query = base_query.filter(time_window_q)

        if has_query_filters:
            base_query = base_query.filter(query)

        return (
            base_query
            .values('id', 'location__longitude', 'location__latitude', 'city', 'location__province', 'severity')
            .distinct()
        )

    def _extract_batch_id(self, data: Mapping[str, Any]) -> Optional[str]:
        raw: Any = (
            data.get("batch_id")
            or data.get("batch")
            or data.get("dataset_id")
            or data.get("dataset")
        )
        if raw in (None, "", [], {}):
            return None

        if isinstance(raw, dict):
            raw = raw.get("value") or raw.get("id") or raw.get("batch") or raw.get("data_id")

        if isinstance(raw, (list, tuple, set)):
            raw = next((item for item in raw if item not in (None, "")), None)
            if raw is None:
                return None

        try:
            return str(UUID(str(raw)))
        except (ValueError, TypeError):
            raise CaseFilterValidationError(
                "Invalid batch identifier.",
                code="invalid_batch",
                fields={"batch": ["Batch identifier must be a valid UUID."]},
            )

    # --- Public wrappers ------------------------------------------------

    def parse_time_params(
        self,
        params: Union[Mapping[str, Any], QueryDict, Dict[str, Any]],
        *,
        start_key: str = DateRangeFilter.DEFAULT_START_KEY,
        end_key: str = DateRangeFilter.DEFAULT_END_KEY,
        period_key: str = DateRangeFilter.DEFAULT_PERIOD_KEY,
        tz_key: str = DateRangeFilter.DEFAULT_TZ_KEY,
        timezone=None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        try:
            return self.time_filter.parse_time_params(
                params,
                start_key=start_key,
                end_key=end_key,
                period_key=period_key,
                tz_key=tz_key,
                timezone=timezone,
                now=now,
            )
        except TimeWindowError as error:
            raise CaseFilterValidationError.from_time_error(error) from error

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
        service = cls(time_filter=DateRangeFilter())
        try:
            start_utc, end_utc = service._resolve_time_range(
                params,
                start_key=start_key,
                end_key=end_key,
                period_key=period_key,
                tz_key=tz_key,
                timezone=timezone,
                now=now,
            )
        except TimeWindowError as error:
            raise CaseFilterValidationError.from_time_error(error) from error

        if not start_utc and not end_utc:
            return None
        if return_type == "tuple":
            return start_utc, end_utc
        return {"start": start_utc, "end": end_utc}

    @classmethod
    def time_window(
        cls,
        data: Mapping[str, Any],
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
        return cls(time_filter=DateRangeFilter())._build_time_window_predicate(
            data,
            field=field,
            start_key=start_key,
            end_key=end_key,
            timezone=timezone,
            null_guard_field=null_guard_field,
            period_key=period_key,
            tz_key=tz_key,
            now=now,
        )

    @classmethod
    def resolve_time_window(
        cls,
        data: Mapping[str, Any],
        *,
        start_key: str = DateRangeFilter.DEFAULT_START_KEY,
        end_key: str = DateRangeFilter.DEFAULT_END_KEY,
        period_key: str = DateRangeFilter.DEFAULT_PERIOD_KEY,
        tz_key: str = DateRangeFilter.DEFAULT_TZ_KEY,
        timezone=None,
        now: Optional[datetime] = None,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        service = cls(time_filter=DateRangeFilter())
        return service._resolve_time_range(
            data,
            start_key=start_key,
            end_key=end_key,
            period_key=period_key,
            tz_key=tz_key,
            timezone=timezone,
            now=now,
        )

    # --- Internals ------------------------------------------------------

    def _get_time_window_q(self, data: Mapping[str, Any]) -> Optional[Q]:
        try:
            start_utc, end_utc = self._resolve_time_range(data)
        except TimeWindowError as error:
            raise CaseFilterValidationError.from_time_error(error) from error

        cache_key = self._make_time_cache_key(start_utc, end_utc)
        if cache_key is None:
            return None

        if cache_key in self._time_window_cache:
            return self._time_window_cache[cache_key]

        predicate = self.time_filter.build_time_predicate(
            self._time_field,
            start_utc,
            end_utc,
            null_guard_field=self._time_null_guard,
        )
        self._store_time_window(cache_key, predicate)
        return predicate

    def _resolve_time_range(
        self,
        data: Mapping[str, Any],
        *,
        start_key: str = DateRangeFilter.DEFAULT_START_KEY,
        end_key: str = DateRangeFilter.DEFAULT_END_KEY,
        period_key: str = DateRangeFilter.DEFAULT_PERIOD_KEY,
        tz_key: str = DateRangeFilter.DEFAULT_TZ_KEY,
        timezone=None,
        now: Optional[datetime] = None,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        return self.time_filter.resolve_time_range(
            data,
            start_key=start_key,
            end_key=end_key,
            period_key=period_key,
            tz_key=tz_key,
            timezone=timezone,
            now=now,
        )

    def _build_time_window_predicate(
        self,
        data: Mapping[str, Any],
        *,
        field: str,
        start_key: str,
        end_key: str,
        timezone,
        null_guard_field: Optional[str],
        period_key: str,
        tz_key: str,
        now: Optional[datetime],
    ) -> Optional[Q]:
        start_utc, end_utc = self._resolve_time_range(
            data,
            start_key=start_key,
            end_key=end_key,
            period_key=period_key,
            tz_key=tz_key,
            timezone=timezone,
            now=now,
        )
        return self.time_filter.build_time_predicate(
            field,
            start_utc,
            end_utc,
            null_guard_field=null_guard_field,
        )

    def _make_time_cache_key(
        self,
        start_utc: Optional[datetime],
        end_utc: Optional[datetime],
    ) -> Optional[Tuple[Optional[str], Optional[str]]]:
        if not start_utc and not end_utc:
            return None
        return (
            start_utc.isoformat() if start_utc else None,
            end_utc.isoformat() if end_utc else None,
        )

    def _store_time_window(
        self,
        key: Tuple[Optional[str], Optional[str]],
        predicate: Optional[Q],
    ) -> None:
        self._time_window_cache[key] = predicate
        self._time_window_cache.move_to_end(key)
        while len(self._time_window_cache) > self._time_window_cache_size:
            self._time_window_cache.popitem(last=False)
