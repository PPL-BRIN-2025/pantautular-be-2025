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
    
class NationalNewsStatisticsReport:
    """Generates statistics about national news portals"""
    
    def generate_report(self, filtered_cases=None):
        """Generate national news statistics report"""
        if not filtered_cases:
            return {
                "top_national": [],
                "all_national": []
            }
        
        # Dictionary to track news portals and their counts
        portal_counts = {}
        
        # Dictionary to track unique diseases per portal
        portal_diseases = {}
        
        # Process all cases
        for case in filtered_cases:
            portal = case.get("news__portal")
            news_type = case.get("news__type")
            disease = case.get("disease__name")
            
            # Only process national news
            if news_type == "Nasional" and portal:
                # Initialize if this is first time seeing this portal
                if portal not in portal_counts:
                    portal_counts[portal] = 0
                    portal_diseases[portal] = set()
                
                # Increment count for this portal
                portal_counts[portal] += 1
                
                # Add disease to set of diseases for this portal
                if disease:
                    portal_diseases[portal].add(disease)
        
        # Format for top_national return
        top_national = [
            {"portal": portal, "count": count}
            for portal, count in portal_counts.items()
        ]
        
        # Sort by count descending
        top_national.sort(key=lambda x: x["count"], reverse=True)
        
        # Format for all_national return
        all_national = [
            {
                "portal": portal,
                "news_count": count,
                "disease_count": len(portal_diseases.get(portal, []))
            }
            for portal, count in portal_counts.items()
        ]
        
        return {
            "top_national": top_national,
            "all_national": all_national
        }