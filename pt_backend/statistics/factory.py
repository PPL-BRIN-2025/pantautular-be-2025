from pt_backend.repositories import CaseRepository
from pt_backend.statistics.reports.prevalence import PrevalenceStatistics
from pt_backend.statistics.interface import ReportStrategy
from pt_backend.statistics.reports.age_grouping import AgeGroupingReport
from pt_backend.statistics.reports.gender_grouping import GenderGroupingReport
from pt_backend.statistics.reports.healthcare_news import HealthcareNewsStatisticsReport
from pt_backend.statistics.reports.local_portal import LocalPortalStatisticsReport
from pt_backend.statistics.reports.national_news import NationalNewsStatisticsReport
from pt_backend.statistics.reports.severity_dates_count import SeverityDatesCountReport
from pt_backend.statistics.reports.severity_grouping import SeverityGroupingReport


class ReportFactory:
    @staticmethod
    def get_all() -> dict[str, ReportStrategy]:
        return {
            "prevalence_statistics": PrevalenceStatistics(repository=CaseRepository()),
            "age_statistics": AgeGroupingReport(),
            "gender_statistics": GenderGroupingReport(),
            "severity_statistics": SeverityGroupingReport(),
            "severity_dates_count_statistics": SeverityDatesCountReport(),
            "national_news_statistics": NationalNewsStatisticsReport(),
            "local_portal_statistics": LocalPortalStatisticsReport(),
            "healthcare_news_statistics": HealthcareNewsStatisticsReport(),
        }