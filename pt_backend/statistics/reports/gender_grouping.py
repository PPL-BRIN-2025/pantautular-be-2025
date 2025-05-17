from ..interface import ReportStrategy
from collections import Counter

class GenderGroupingReport(ReportStrategy):
    """Generates gender distribution statistics"""

    def generate_report(self, filtered_cases=None):
        """Generate gender distribution report"""
        gender_counts = Counter()
        counted_cases = set()

        if not filtered_cases:
            return {"male": 0, "female": 0}

        for case in filtered_cases:
            if not case or not isinstance(case, dict):
                continue
                
            case_id = case.get("id")
            
            if case_id in counted_cases:
                continue
                
            counted_cases.add(case_id)
            
            gender = case.get("gender")
            if isinstance(gender, str):
                gender = gender.lower()
                if gender in ["male", "female"]:
                    gender_counts[gender] += 1

        return {
            "male": gender_counts.get("male", 0),
            "female": gender_counts.get("female", 0),
        }