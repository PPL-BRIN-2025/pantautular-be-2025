from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
from typing import Any, Dict, Mapping, Optional, Tuple, Union

import pytz
from django.db.models import Q
from django.utils.dateparse import parse_datetime as django_parse_datetime
from pytz import UnknownTimeZoneError


class TimeWindowError(ValueError):
    """Uniform error for time-window validation and parsing failures."""

    def __init__(self, message: str, *, fields: Optional[Dict[str, list]] = None):
        super().__init__(message)
        self.fields = fields or {}


@dataclass(frozen=True)
class _PeriodResolution:
    """SRP: Carry the result of resolving a period input."""

    delta: Optional[timedelta] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class DateRangeFilter:
    """
    Date filter with SOLID-friendly helpers.

    - SRP: Each helper focuses on a single responsibility (parsing, resolving, validating, etc.).
    - OCP: Behaviour is extended via alias dictionaries and overridable hooks instead of editing callers.
    - LSP: Public helpers always return predictable types (aware UTC datetimes, Q objects).
    - ISP: CaseFilterService consumes only parse/resolve/build interfaces.
    - DIP: External collaborators can inject customised implementations.
    """

    DEFAULT_START_KEY = "start_date"
    DEFAULT_END_KEY = "end_date"
    DEFAULT_PERIOD_KEY = "period"
    DEFAULT_TZ_KEY = "timezone"

    PERIOD_UNITS = {
        "m": "minutes",
        "min": "minutes",
        "mins": "minutes",
        "minute": "minutes",
        "minutes": "minutes",
        "h": "hours",
        "hr": "hours",
        "hrs": "hours",
        "hour": "hours",
        "hours": "hours",
        "d": "days",
        "day": "days",
        "days": "days",
        "w": "weeks",
        "wk": "weeks",
        "wks": "weeks",
        "week": "weeks",
        "weeks": "weeks",
    }

    DEFAULT_PERIOD_ALIASES: Dict[str, Union[Tuple[int, str], Any]] = {
        "1h": (1, "hours"),
        "24h": (24, "hours"),
        "1d": (1, "days"),
        "7d": (7, "days"),
    }

    def __init__(
        self,
        *,
        max_span_days: Optional[int] = None,
        period_aliases: Optional[Dict[str, Union[Tuple[int, str], Any]]] = None,
    ):
        self.max_span_days = max_span_days
        aliases = dict(self.DEFAULT_PERIOD_ALIASES)
        if period_aliases:
            aliases.update({k.lower(): v for k, v in period_aliases.items()})
        self.period_aliases = aliases

    # --- Public API -----------------------------------------------------

    def apply(self, data: Mapping[str, Any]) -> Q:
        """SRP: Compute the filter predicate for the default news timestamp."""
        predicate = self.build_time_window(
            field="news__date_published",
            data=data,
            null_guard_field="news",
        )
        return predicate if predicate is not None else Q()

    def parse_time_params(
        self,
        params: Mapping[str, Any],
        *,
        start_key: str = DEFAULT_START_KEY,
        end_key: str = DEFAULT_END_KEY,
        period_key: str = DEFAULT_PERIOD_KEY,
        tz_key: str = DEFAULT_TZ_KEY,
        timezone=None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """ISP: Expose a minimal parser for consumers that only need sanitised request data."""
        raw = self._collect_raw_params(params, start_key, end_key, period_key, tz_key)
        start_utc, end_utc = self.resolve_time_range(
            raw,
            start_key=start_key,
            end_key=end_key,
            period_key=period_key,
            tz_key=tz_key,
            timezone=timezone,
            now=now,
            _is_raw=True,
        )

        payload: Dict[str, Any] = {}
        if start_utc:
            payload[start_key] = start_utc.isoformat()
        if end_utc:
            payload[end_key] = end_utc.isoformat()
        if raw.get(tz_key):
            payload[tz_key] = raw[tz_key]
        if raw.get(period_key):
            payload[period_key] = raw[period_key]
        return payload

    def resolve_time_range(
        self,
        params: Mapping[str, Any],
        *,
        start_key: str = DEFAULT_START_KEY,
        end_key: str = DEFAULT_END_KEY,
        period_key: str = DEFAULT_PERIOD_KEY,
        tz_key: str = DEFAULT_TZ_KEY,
        timezone=None,
        now: Optional[datetime] = None,
        _is_raw: bool = False,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """SRP: Convert inputs into a UTC-aware (start, end) tuple."""
        raw = dict(params) if _is_raw else self._collect_raw_params(
            params,
            start_key,
            end_key,
            period_key,
            tz_key,
        )

        tz = self.resolve_timezone(raw.get(tz_key), timezone or pytz.UTC)
        start_local = self._parse_datetime_value(raw.get(start_key), tz, start_key)
        end_local = self._parse_datetime_value(raw.get(end_key), tz, end_key)

        period_resolution = self.resolve_period(
            raw.get(period_key),
            period_key=period_key,
            now=now,
            tz=tz,
        )

        if period_resolution.start or period_resolution.end:
            if period_resolution.start:
                start_local = period_resolution.start
            if period_resolution.end:
                end_local = period_resolution.end
        elif period_resolution.delta:
            start_local, end_local = self.apply_period(
                start_date=start_local,
                end_date=end_local,
                period=period_resolution.delta,
                tz=tz,
                now=now,
            )

        start_utc, end_utc = self.normalize(start_local, end_local, tz)
        self.validate(
            start=start_utc,
            end=end_utc,
            start_key=start_key,
            end_key=end_key,
            max_span_days=self.max_span_days,
            now=now,
        )
        return start_utc, end_utc

    def build_time_predicate(
        self,
        ts_field: str,
        start_utc: Optional[datetime],
        end_utc: Optional[datetime],
        *,
        null_guard_field: Optional[str] = None,
    ) -> Optional[Q]:
        """LSP: Always returns a Q object or None using UTC-aware datetimes."""
        if not start_utc and not end_utc:
            return None

        if start_utc and end_utc:
            predicate = Q(**{f"{ts_field}__range": [start_utc, end_utc]})
        elif start_utc:
            predicate = Q(**{f"{ts_field}__gte": start_utc})
        else:
            predicate = Q(**{f"{ts_field}__lte": end_utc})

        if null_guard_field:
            predicate &= Q(**{f"{null_guard_field}__isnull": False})

        return predicate

    def build_time_window(
        self,
        field: str,
        data: Mapping[str, Any],
        *,
        start_key: str = DEFAULT_START_KEY,
        end_key: str = DEFAULT_END_KEY,
        timezone=None,
        null_guard_field: Optional[str] = None,
        period_key: str = DEFAULT_PERIOD_KEY,
        tz_key: str = DEFAULT_TZ_KEY,
        now: Optional[datetime] = None,
    ) -> Optional[Q]:
        """SRP: Backwards-compatible helper used by existing filter strategies."""
        start_utc, end_utc = self.resolve_time_range(
            data,
            start_key=start_key,
            end_key=end_key,
            period_key=period_key,
            tz_key=tz_key,
            timezone=timezone,
            now=now,
        )
        return self.build_time_predicate(
            field,
            start_utc,
            end_utc,
            null_guard_field=null_guard_field,
        )

    @classmethod
    def resolve_time_window(
        cls,
        data: Mapping[str, Any],
        *,
        start_key: str = DEFAULT_START_KEY,
        end_key: str = DEFAULT_END_KEY,
        period_key: str = DEFAULT_PERIOD_KEY,
        tz_key: str = DEFAULT_TZ_KEY,
        timezone=None,
        now: Optional[datetime] = None,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Backward-compatible alias."""
        return cls().resolve_time_range(
            data,
            start_key=start_key,
            end_key=end_key,
            period_key=period_key,
            tz_key=tz_key,
            timezone=timezone,
            now=now,
        )

    # --- Hooks for extension --------------------------------------------

    def resolve_period(
        self,
        period_value: Optional[Union[str, Dict[str, Union[int, str]]]],
        *,
        period_key: str,
        now: Optional[datetime],
        tz,
    ) -> _PeriodResolution:
        """OCP: Resolve custom period expressions or aliases without changing callers."""
        if not period_value:
            return _PeriodResolution()

        now_local = self.ensure_timezone(now or datetime.now(pytz.UTC), tz)

        if isinstance(period_value, str):
            alias_key = period_value.strip().lower()
            if alias_key in self.period_aliases:
                alias = self.period_aliases[alias_key]
                if callable(alias):
                    result = alias(now_local, tz)
                    return self._normalize_period_alias_result(result, tz, period_key)
                value, unit = alias  # type: ignore[misc]
                return _PeriodResolution(delta=timedelta(**{unit: value}))

        delta = self.parse_period(period_value)
        if delta:
            return _PeriodResolution(delta=delta)

        raise TimeWindowError(
            "Invalid period value.",
            fields={period_key: ["Unsupported period format."]},
        )

    def validate(
        self,
        *,
        start: Optional[datetime],
        end: Optional[datetime],
        start_key: str,
        end_key: str,
        max_span_days: Optional[int],
        now: Optional[datetime],
    ) -> None:
        """OCP: Centralised validation that callers can override or extend."""
        if start and end and start > end:
            raise TimeWindowError(
                "Start date must be before end date.",
                fields={
                    start_key: ["Must be earlier than end date."],
                    end_key: ["Must be later than start date."],
                },
            )

        if max_span_days and start and end:
            max_span = timedelta(days=max_span_days)
            if end - start > max_span:
                raise TimeWindowError(
                    "Selected date range exceeds the allowed span.",
                    fields={
                        start_key: [f"Span must be <= {max_span_days} days."],
                        end_key: [f"Span must be <= {max_span_days} days."],
                    },
                )

        if start and now and start > now:
            raise TimeWindowError(
                "Start date cannot be in the future.",
                fields={start_key: ["Must be on or before current time."]},
            )

    def normalize(
        self,
        start: Optional[datetime],
        end: Optional[datetime],
        tz,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """SRP: Convert local datetimes to UTC-aware values."""
        normalized_start = self.ensure_timezone(start, tz)
        normalized_end = self.ensure_timezone(end, tz)

        if normalized_start:
            normalized_start = self.normalize_to_utc(normalized_start)
        if normalized_end:
            normalized_end = self.normalize_to_utc(normalized_end)
        return normalized_start, normalized_end

    # --- Utility helpers ------------------------------------------------

    def _collect_raw_params(
        self,
        params: Mapping[str, Any],
        start_key: str,
        end_key: str,
        period_key: str,
        tz_key: str,
    ) -> Dict[str, Any]:
        """SRP: Extract raw inputs without interpretation."""
        return {
            start_key: self._extract_value(params, start_key),
            end_key: self._extract_value(params, end_key),
            period_key: self._extract_value(params, period_key),
            tz_key: self._extract_value(params, tz_key),
        }

    def _extract_value(self, params: Mapping[str, Any], key: str) -> Any:
        if hasattr(params, "getlist"):
            values = params.getlist(key)  # type: ignore[attr-defined]
            return self._first_non_empty(values)
        if hasattr(params, "get"):
            return self._first_non_empty(params.get(key))
        return self._first_non_empty(getattr(params, key, None))

    def _parse_datetime_value(
        self,
        value: Optional[str],
        tz,
        field_name: str,
    ) -> Optional[datetime]:
        """SRP: Parse a single datetime field with consistent error handling."""
        if value is None:
            return None
        parsed = self.parse_datetime(value, tz)
        if parsed is None:
            raise TimeWindowError(
                f"Invalid {field_name.replace('_', ' ')} format.",
                fields={field_name: ["Invalid datetime format."]},
            )
        return parsed

    def _normalize_period_alias_result(self, result: Any, tz, period_key: str) -> _PeriodResolution:
        if isinstance(result, tuple):
            start, end = result
            return _PeriodResolution(
                start=self.ensure_timezone(start, tz),
                end=self.ensure_timezone(end, tz),
            )
        if isinstance(result, timedelta):
            return _PeriodResolution(delta=result)
        raise TimeWindowError(
            "Invalid period alias result.",
            fields={period_key: ["Alias resolver must return timedelta or (start, end)."]},
        )

    @staticmethod
    def resolve_timezone(
        tz_identifier: Optional[Union[str, tzinfo]],
        default_tz,
    ):
        if isinstance(tz_identifier, str):
            try:
                return pytz.timezone(tz_identifier)
            except UnknownTimeZoneError:
                return default_tz
        if hasattr(tz_identifier, "utcoffset"):
            return tz_identifier
        return default_tz

    @classmethod
    def parse_datetime(cls, date_str: Optional[str], tz) -> Optional[datetime]:
        """SRP: Preserve backwards-compatible static parser."""
        if not date_str:
            return None

        dt = django_parse_datetime(date_str)
        if dt is None:
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue

        if dt is None:
            return None

        if dt.tzinfo is None:
            if hasattr(tz, "localize"):
                dt = tz.localize(dt)  # type: ignore[attr-defined]
            else:
                dt = dt.replace(tzinfo=tz)
        else:
            dt = dt.astimezone(tz)

        return dt

    @classmethod
    def apply_period(
        cls,
        *,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        period: timedelta,
        tz,
        now: Optional[datetime] = None,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """SRP: Apply a resolved timedelta to produce missing bounds."""
        if period <= timedelta(0):
            return start_date, end_date

        reference_now = cls.ensure_timezone(now, tz) if now else datetime.now(tz)

        if start_date and not end_date:
            end_date = start_date + period
        elif end_date and not start_date:
            start_date = end_date - period
        elif not start_date and not end_date:
            end_date = reference_now
            start_date = reference_now - period
        return start_date, end_date

    @staticmethod
    def ensure_timezone(dt: Optional[datetime], tz):
        if dt is None:
            return None
        if dt.tzinfo is None:
            if hasattr(tz, "localize"):
                return tz.localize(dt)  # type: ignore[attr-defined]
            return dt.replace(tzinfo=tz)
        return dt.astimezone(tz)

    @staticmethod
    def normalize_to_utc(dt: datetime) -> datetime:
        return dt.astimezone(pytz.UTC)

    def parse_period(self, period: Union[str, Dict[str, Union[int, str]]]) -> Optional[timedelta]:
        """SRP: Parse ad-hoc period inputs beyond aliases."""
        if isinstance(period, dict):
            value = period.get("value")
            unit = period.get("unit")
            if isinstance(value, int) and isinstance(unit, str):
                unit_key = self.PERIOD_UNITS.get(unit.lower())
                if unit_key:
                    return timedelta(**{unit_key: value})
            return None

        if isinstance(period, str):
            period = period.strip()
            if not period:
                return None
            if period.isdigit():
                return timedelta(days=int(period))
            for suffix in sorted(self.PERIOD_UNITS, key=len, reverse=True):
                if period.lower().endswith(suffix):
                    value_part = period[: -len(suffix)].strip()
                    if value_part.isdigit():
                        unit_key = self.PERIOD_UNITS[suffix]
                        return timedelta(**{unit_key: int(value_part)})
        return None

    @staticmethod
    def _first_non_empty(value: Any) -> Any:
        if isinstance(value, str):
            return value if value.strip() != "" else None
        if isinstance(value, (list, tuple)):
            for item in value:
                if item not in (None, ""):
                    return item
            return None
        return value
