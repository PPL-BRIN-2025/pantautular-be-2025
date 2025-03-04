from .repositories import CaseRepository
from .interfaces import CaseRetreivalInterface

class CaseService(CaseRetreivalInterface):
    @staticmethod
    def get_all_case_locations():
        return CaseRepository.get_all_case_locations()