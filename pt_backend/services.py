from .repositories import CaseRepository
from .interfaces import CaseRetreivalInterface

class CaseService(CaseRetreivalInterface):
    def get_all_case_locations(self):
        return CaseRepository.get_all_case_locations()
