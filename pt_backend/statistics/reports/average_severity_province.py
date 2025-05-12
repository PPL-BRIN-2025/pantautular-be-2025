
# from pt_backend.repositories import CaseRepository
# from pt_backend.services import CacheService, CaseService
# from pt_backend.statistic import AverageSeverityByProvince
# from pt_backend.statistics.interface import ReportStrategy


# class AverageSeverityByProvinceReport(ReportStrategy):
#     def __init__(self):
#         cs = CaseService(repository=CaseRepository(),
#                          cache_service=CacheService()) 
#         self.analyzer = AverageSeverityByProvince(cs)

#     def generate_report(self, filtered_cases=None, **kwargs):
#         return self.analyzer.compute()