from pt_backend.statistics.factory import ReportFactory
from pt_backend.statistics.reports.prevalence import PrevalenceStatistics

class StatisticsCoordinator:
    def __init__(self, case_filter_service):
        self.case_filter_service = case_filter_service
        self.strategies = ReportFactory.get_all()

    def generate_comprehensive_report(self, **filters):
        # filter data
        try:
            if self.case_filter_service:
                filtered = self.case_filter_service.filter_cases(**filters)
            else:
                filtered = []
        except Exception as e:
            return {"error": f"Failed to filter cases: {e}"}

        date_range = filters.get('date_range')
        start_date = filters.get('start_date')

        if not start_date and isinstance(date_range, dict):
            start_date = date_range.get('start')

        prevalence_kwargs = {
            "filtered_cases": filtered,
            "date_range": date_range,
            "start_date": start_date,
        }

        out = {}
        for name, strategy in self.strategies.items():
            try:
                if isinstance(strategy, PrevalenceStatistics):
                    # Khusus untuk PrevalenceStatistics, kita perlu mengoper start_date
                    out[name] = strategy.generate_report(**prevalence_kwargs)
                else:
                    # Strategy diharapkan menerima arg named filtered_cases
                    out[name] = strategy.generate_report(filtered_cases=filtered)
            except Exception as e:
                out[name] = {"error": f"Failed to generate report: {e}"}

        return out