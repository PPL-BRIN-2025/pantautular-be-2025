from .interfaces import CaseRetrievalInterface, CaseRepositoryInterface

class CaseService(CaseRetrievalInterface):
    def __init__(self, repository: CaseRepositoryInterface):
        self.repository = repository

    def get_all_case_locations(self):
        locations = self.repository.get_all_locations()
        return locations if locations else []
