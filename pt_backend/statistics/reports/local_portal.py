from ..interface import ReportStrategy
from collections import Counter, defaultdict

class LocalPortalStatisticsReport(ReportStrategy):
    """Generates local portal statistics"""

    def generate_report(self, filtered_cases=None):
        """
        Generates local portal statistics report

        Returns:
            dict: Contains two keys:
                - top_local: List of portals sorted by news count
                - all_local: List of portals with news and disease counts
        """
        if not filtered_cases:
            return {
                "top_local": [],
                "all_local": []
            }
        
        portal_diseases = defaultdict(set)
        portal_counts = Counter()

        # Process local news only
        for case in filtered_cases:
            portal = case.get("news__portal")
            news_type = case.get("news__type")
            disease = case.get("disease__name")

            # Skip non-local or missing portal news
            if not (portal and news_type and news_type.lower() == "lokal"):
                continue

            # Count this news article
            portal_counts[portal] += 1

            # Add disease if present
            if disease:
                portal_diseases[portal].add(disease)
        
        top_local = [
            {"portal": portal, "count": count}
            for portal, count in portal_counts.most_common(5)
        ]

        all_local = [
            {
                "portal": portal,
                "news_count": count,
                "disease_count": len(portal_diseases[portal])
            }
            for portal, count in portal_counts.items()
        ]

        return {
            "top_local": top_local,
            "all_local": all_local
        }