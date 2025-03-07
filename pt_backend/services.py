from .repositories import CaseRepository
from .interfaces import CaseRetrievalInterface

class CaseService(CaseRetrievalInterface):
    def get_all_case_locations(self):
        return CaseRepository.get_all_case_locations()
