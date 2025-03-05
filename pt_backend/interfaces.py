from abc import ABC, abstractmethod

class CaseRetreivalInterface(ABC):
    @abstractmethod
    def get_all_case_locations(self):
        pass
