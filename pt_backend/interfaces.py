from abc import ABC, abstractmethod

class CaseRetrievalInterface(ABC):
    @abstractmethod
    def get_all_cases(self):
        pass # pragma: no cover
    @abstractmethod
    def get_all_case_locations(self):
        pass # pragma: no cover
    @abstractmethod
    def get_cases_by_year(self, year):
        pass # pragma: no cover
    
class CaseRepositoryInterface(ABC):
    @abstractmethod
    def get_all_cases(self):
        pass
    
    @abstractmethod
    def get_all_locations(self):
        pass # pragma: no cover

    @abstractmethod
    def get_case_detail_by_id(self, case_id):
        pass # pragma: no cover

    @abstractmethod
    def get_cases_by_year(self, year):
        pass # pragma: no cover

class CacheInterface(ABC):
    @abstractmethod
    def get(self, key):
        pass # pragma: no cover

    @abstractmethod
    def set(self, key, value, timeout):
        pass # pragma: no cover

    @abstractmethod
    def delete(self, key):
        pass # pragma: no cover