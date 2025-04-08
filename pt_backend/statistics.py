from collections import Counter

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

class GenderGroupingReport:
    """Generates gender distribution statistics"""

    def generate_report(self, filtered_cases=None):
        """Generate gender distribution report"""
        gender_counts = Counter()

        if not filtered_cases:
            return {"male": 0, "female": 0}

        for case in filtered_cases:
            if case and isinstance(case, dict):
                gender = case.get("gender")
                if isinstance(gender, str):  # Pastikan gender adalah string
                    gender = gender.lower()
                    if gender in ["male", "female"]:
                        gender_counts[gender] += 1

        return {
            "male": gender_counts.get("male", 0),
            "female": gender_counts.get("female", 0),
        }