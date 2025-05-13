from collections import Counter
from ..interface import ReportStrategy


class SeverityGroupingReport(ReportStrategy):
 
    def generate_report(self, filtered_cases = None):
        severity_counts = Counter()
        total_cases = 0
        
        if filtered_cases:
            for case in filtered_cases:
                total_cases += 1
                severity = case.get("severity")
                if severity is not None:
                    severity_counts[severity] += 1
        
        return {
            "total_cases": total_cases,
            "severity_counts": dict(severity_counts)
        }
