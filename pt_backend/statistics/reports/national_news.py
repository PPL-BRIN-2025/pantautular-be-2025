from ..interface import ReportStrategy
from collections import Counter, defaultdict

class NationalNewsStatisticsReport(ReportStrategy):
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
            for portal, count in portal_counts.most_common(5)
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