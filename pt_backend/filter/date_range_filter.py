from datetime import datetime
import pytz
from django.db.models import Q
from typing import Dict, Optional

class DateRangeFilter:
    def apply(self, data: Dict) -> Q:
        utc = pytz.UTC

        start_date = self.parse_datetime(data.get("start_date"), utc)
        end_date = self.parse_datetime(data.get("end_date"), utc)

        if start_date and end_date:
            return Q(news__date_published__range=[start_date, end_date]) & Q(news__isnull=False)
        elif start_date:
            return Q(news__date_published__gte=start_date) & Q(news__isnull=False)
        elif end_date:
            return Q(news__date_published__lte=end_date) & Q(news__isnull=False)
        else:
            return Q()

    def parse_datetime(self, date_str: Optional[str], timezone) -> Optional[datetime]:
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
