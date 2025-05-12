from collections import Counter
from ..interface import ReportStrategy


class SeverityGroupingReport(ReportStrategy):
 
    def generate_report(self, filtered_cases = None):
        severity_counts = Counter()
        total_cases = 0
        counted_cases = set()
        
        if filtered_cases:
            for case in filtered_cases:
                case_id = case.get("id")

                if case_id in counted_cases:
                    continue

                counted_cases.add(case_id)
                total_cases += 1
                
                severity = case.get("severity")
                if severity is not None:
                    severity_counts[severity] += 1
        
        return {
            "total_cases": total_cases,
            "severity_counts": dict(severity_counts)
        }
