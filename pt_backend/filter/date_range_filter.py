from datetime import datetime
import pytz
from django.db.models import Q
from typing import Dict
from typing import Optional

class DateRangeFilter:
    def apply(self, data: Dict) -> Q:
        if "start_date" not in data or "end_date" not in data:
            return Q()
        
        utc = pytz.UTC
        start_date = self.parse_datetime(data["start_date"], utc)
        end_date = self.parse_datetime(data["end_date"], utc)

        if not start_date or not end_date:
            return Q() 

        return Q(news__date_published__range=[start_date, end_date]) & Q(news__isnull=False)

    def parse_datetime(self, date_str: str, timezone) -> Optional[datetime]:
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",  # Format ISO 8601 dengan milidetik
            "%Y-%m-%dT%H:%M:%SZ",      # Format ISO 8601 tanpa milidetik
            "%Y-%m-%d %H:%M:%S",       # Format biasa dengan spasi
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone)
            except ValueError:
                continue
        return None  