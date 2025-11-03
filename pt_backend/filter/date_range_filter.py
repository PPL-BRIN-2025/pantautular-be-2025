from datetime import datetime, timedelta, tzinfo
from typing import Dict, Optional, Tuple, Union

import pytz
from django.db.models import Q
from django.utils.dateparse import parse_datetime as django_parse_datetime
from pytz import UnknownTimeZoneError


class TimeWindowError(ValueError):
    def __init__(self, message: str, *, fields: Optional[Dict[str, list]] = None):
        super().__init__(message)
        self.fields = fields or {}


class DateRangeFilter:
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

    def apply(self, data: Dict) -> Q:
        time_window = self.build_time_window(
            field="news__date_published",
            data=data,
            null_guard_field="news",
        )
        if time_window is not None:
            return time_window
        return Q()

    @classmethod
    def build_time_window(
        cls,
        field: str,
        data: Dict,
        *,
        start_key: str = DEFAULT_START_KEY,
        end_key: str = DEFAULT_END_KEY,
        timezone=None,
        null_guard_field: Optional[str] = None,
        period_key: str = DEFAULT_PERIOD_KEY,
        tz_key: str = DEFAULT_TZ_KEY,
        now: Optional[datetime] = None,
    ) -> Optional[Q]:
        start_date, end_date = cls.resolve_time_window(
            data,
            start_key=start_key,
            end_key=end_key,
            period_key=period_key,
            tz_key=tz_key,
            timezone=timezone,
            now=now,
        )

        if start_date and end_date:
            time_window = Q(**{f"{field}__range": [start_date, end_date]})
        elif start_date:
            time_window = Q(**{f"{field}__gte": start_date})
        elif end_date:
            time_window = Q(**{f"{field}__lte": end_date})
        else:
            return None

        if null_guard_field:
            time_window &= Q(**{f"{null_guard_field}__isnull": False})

        return time_window

    @classmethod
    def resolve_time_window(
        cls,
        data: Dict,
        *,
        start_key: str = DEFAULT_START_KEY,
        end_key: str = DEFAULT_END_KEY,
        period_key: str = DEFAULT_PERIOD_KEY,
        tz_key: str = DEFAULT_TZ_KEY,
        timezone=None,
        now: Optional[datetime] = None,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        fallback_tz = timezone or pytz.UTC
        tz = cls.resolve_timezone(data.get(tz_key), fallback_tz)

        start_raw = data.get(start_key)
        end_raw = data.get(end_key)
        period_raw = data.get(period_key)

        start_date = cls.parse_datetime(start_raw, tz)
        end_date = cls.parse_datetime(end_raw, tz)
        period_delta = cls.parse_period(period_raw) if period_raw else None

        if start_raw and start_date is None:
            raise TimeWindowError(
                "Invalid start date format.",
                fields={start_key: ["Invalid datetime format."]},
            )
        if end_raw and end_date is None:
            raise TimeWindowError(
                "Invalid end date format.",
                fields={end_key: ["Invalid datetime format."]},
            )
        if period_raw and period_delta is None:
            raise TimeWindowError(
                "Invalid period value.",
                fields={period_key: ["Unsupported period format."]},
            )

        if period_delta:
            start_date, end_date = cls.apply_period(
                start_date=start_date,
                end_date=end_date,
                period=period_delta,
                tz=tz,
                now=now,
            )

        start_utc = cls.normalize_to_utc(start_date) if start_date else None
        end_utc = cls.normalize_to_utc(end_date) if end_date else None

        if start_utc and end_utc and start_utc > end_utc:
            raise TimeWindowError(
                "Start date must be before end date.",
                fields={
                    start_key: ["Must be earlier than end date."],
                    end_key: ["Must be later than start date."],
                },
            )

        return start_utc, end_utc

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

    @classmethod
    def parse_period(cls, period: Union[str, Dict[str, Union[int, str]]]) -> Optional[timedelta]:
        if isinstance(period, dict):
            value = period.get("value")
            unit = period.get("unit")
            if isinstance(value, int) and isinstance(unit, str):
                unit_key = cls.PERIOD_UNITS.get(unit.lower())
                if unit_key:
                    return timedelta(**{unit_key: value})
            return None

        if isinstance(period, str):
            period = period.strip()
            if not period:
                return None
            if period.isdigit():
                # Default to days if only a number is provided.
                return timedelta(days=int(period))
            for suffix in sorted(cls.PERIOD_UNITS, key=len, reverse=True):
                if period.lower().endswith(suffix):
                    value_part = period[: -len(suffix)].strip()
                    if value_part.isdigit():
                        unit_key = cls.PERIOD_UNITS[suffix]
                        return timedelta(**{unit_key: int(value_part)})
        return None
