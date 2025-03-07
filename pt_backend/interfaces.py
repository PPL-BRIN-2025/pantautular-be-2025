from abc import ABC, abstractmethod

class CaseRetrievalInterface(ABC):
    @abstractmethod
    def get_all_case_locations(self):
        pass

class CaseRepositoryInterface(ABC):
    @abstractmethod
    def get_all_locations(self):
        pass

