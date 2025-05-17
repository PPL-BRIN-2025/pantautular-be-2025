from asyncio.log import logger
from collections import defaultdict
from datetime import datetime
from ..interface import ReportStrategy

class SeverityDatesCountReport(ReportStrategy):
    def generate_report(self, filtered_cases=None):
        """Generate severity dates count report"""
        if not filtered_cases:
            logger.info("No filtered cases provided. Returning empty report.")
            return {}

        severity_dates = defaultdict(lambda: defaultdict(int))

        for case in filtered_cases:
            severity = case.get("severity")
            date_published = case.get("news__date_published")

            # Safely format the date
            if isinstance(date_published, datetime):
                date_published = date_published.strftime('%Y-%m-%d')
            else:
                logger.warning(f"Invalid or missing date_published in case: {case}")
                continue

            severity_dates[severity][date_published] += 1

        for severity, dates in severity_dates.items():
            severity_dates[severity] = dict(sorted(dates.items()))

        # Transform to the desired output format
        return {
            severity: [{"date": date, "count": count} for date, count in dates.items()]
            for severity, dates in severity_dates.items()
        }