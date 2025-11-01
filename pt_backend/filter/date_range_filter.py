from datetime import datetime
import pytz
from django.db.models import Q
from typing import Dict, Optional

class DateRangeFilter:
    DEFAULT_START_KEY = "start_date"
    DEFAULT_END_KEY = "end_date"

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
    ) -> Optional[Q]:
        tz = timezone or pytz.UTC

        start_date = cls.parse_datetime(data.get(start_key), tz)
        end_date = cls.parse_datetime(data.get(end_key), tz)

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

    @staticmethod
    def parse_datetime(date_str: Optional[str], timezone) -> Optional[datetime]:
        if not date_str:  # Handle None case
            return None
        
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO 8601 dengan milidetik
            "%Y-%m-%dT%H:%M:%SZ",      # ISO 8601 tanpa milidetik
            "%Y-%m-%d %H:%M:%S",       # Format biasa dengan spasi
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone)
            except ValueError:
                continue
        return None   

