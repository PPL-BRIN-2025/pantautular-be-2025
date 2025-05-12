from ..interface import ReportStrategy
from collections import Counter, defaultdict

class HealthcareNewsStatisticsReport(ReportStrategy):
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
            for portal, count in portal_counts.most_common(5)
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
