from collections import Counter, defaultdict

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
    
class NationalNewsStatisticsReport:
    """Generates statistics about national news portals"""
    
    def generate_report(self, filtered_cases=None):
        """
        Generate national news statistics report
        
        Returns:
            dict: Contains two keys:
                - top_national: List of portals sorted by news count
                - all_national: List of portals with news and disease counts
        """
        # Early return for empty data
        if not filtered_cases:
            return {
                "top_national": [],
                "all_national": []
            }
                
        # Track disease counts per portal
        portal_diseases = defaultdict(set)
        # Track news counts per portal
        portal_counts = Counter()
        
        # Process national news only
        for case in filtered_cases:
            portal = case.get("news__portal")
            news_type = case.get("news__type")
            disease = case.get("disease__name")
            
            # Skip non-national or missing portal news
            if not (portal and news_type == "Nasional"):
                continue
                
            # Count this news article
            portal_counts[portal] += 1
            
            # Add disease if present
            if disease:
                portal_diseases[portal].add(disease)
        
        # No need to sort manually - Counter has most_common() method
        top_national = [
            {"portal": portal, "count": count} 
            for portal, count in portal_counts.most_common()
        ]
        
        # Create all_national with news and disease counts
        all_national = [
            {
                "portal": portal,
                "news_count": count,
                "disease_count": len(portal_diseases[portal])
            }
            for portal, count in portal_counts.items()
        ]
        
        return {
            "top_national": top_national,
            "all_national": all_national
        }

class HealthcareNewsStatisticsReport:
    """Generates statistics about healthcare news portals"""

    def generate_report(self, filtered_cases=None):
        """
        Generate healthcare news statistics report

        Returns:
            dict: Contains two keys:
                - top_healthcare: List of portals sorted by news count
                - all_healthcare: List of portals with news and disease counts
        """
        # Early return for empty data
        if not filtered_cases:
            return {"top_healthcare": [], "all_healthcare": []}

        # Track disease counts per portal
        portal_diseases = defaultdict(set)
        # Track news counts per portal
        portal_counts = Counter()

        # Process healthcare news only
        for case in filtered_cases:
            portal = case.get("news__portal")
            news_type = case.get("news__type")
            disease = case.get("disease__name")

            # Skip non-healthcare or missing portal news
            if not (portal and news_type and news_type.lower() == "kesehatan"):
                continue

            # Count this news article
            portal_counts[portal] += 1

            # Add disease if present
            if disease:
                portal_diseases[portal].add(disease)

        # Create top_healthcare with sorted news counts
        top_healthcare = [
            {"portal": portal, "count": count}
            for portal, count in portal_counts.most_common()
        ]

        # Create all_healthcare with news and disease counts
        all_healthcare = [
            {
                "portal": portal,
                "news_count": count,
                "disease_count": len(portal_diseases[portal])
            }
            for portal, count in portal_counts.items()
        ]

        return {"top_healthcare": top_healthcare, "all_healthcare": all_healthcare}