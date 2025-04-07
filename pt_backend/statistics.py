from collections import Counter
from datetime import datetime

class SeverityGroupingReport:
 
    def __init__(self, case_filter_service):
        self.case_filter_service = case_filter_service

    def generate_report(self, provinces=None, cities=None, news_portals=None, severities=None, news_date_range=None):
        filtered_cases = self.case_filter_service.filter_cases(
            provinces=provinces,
            cities=cities,
            news_portals=news_portals,
            severities=severities,
            news_date_range=news_date_range,
        )
        
        severity_counts = Counter()
        total_cases = 0
        
        for case in filtered_cases:
            total_cases += 1
            severity = case.get("severity")
            if severity is not None:
                severity_counts[severity] += 1
        
        return {
            "total_cases": total_cases,
            "severity_counts": dict(severity_counts)
        }

class AgeGroupingReport:
    """Generates age grouping statistics"""
    
    def generate_report(self, filtered_cases=None):
        """Generate age grouping report"""
        age_groups = {
            "under_12": 0,
            "12_25": 0,
            "26_45": 0,
            "above_45": 0
        }

        if not filtered_cases:
            return age_groups
        
        # Track cases we've already counted
        counted_cases = set()
        
        for case in filtered_cases:
            case_id = case.get("id")
            
            # Skip if we've already counted this case
            if case_id in counted_cases:
                continue
                
            counted_cases.add(case_id)
            
            age = case.get("age")
            if age is None:
                continue
                
            if age < 12:
                age_groups["under_12"] += 1
            elif 12 <= age <= 25:
                age_groups["12_25"] += 1
            elif 26 <= age <= 45:
                age_groups["26_45"] += 1
            else:
                age_groups["above_45"] += 1

        return age_groups

class SeverityDatesCountReport:
    def generate_report(self, filtered_cases=None):
        """Generate severity dates count report"""
        severity_dates = {}
        
        if not filtered_cases:
            return severity_dates
        
        for case in filtered_cases:
            severity = case.get("severity")
            date_published = case.get("news__date_published")
            if isinstance(date_published, datetime):
                date_published = date_published.strftime('%Y-%m-%d')
            
            if severity not in severity_dates:
                severity_dates[severity] = {}
            
            if date_published not in severity_dates[severity]:
                severity_dates[severity][date_published] = 0
            
            severity_dates[severity][date_published] += 1

        result = {}

        for severity, dates in severity_dates.items():
            result[severity] = [
                {"date": date, "count": count} for date, count in dates.items()
            ]
        return result