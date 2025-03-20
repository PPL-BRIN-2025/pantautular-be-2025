from abc import ABC, abstractmethod

class CaseRetrievalInterface(ABC):
    @abstractmethod
    def get_all_case_locations(self):
        pass

class CaseRepositoryInterface(ABC):
    @abstractmethod
    def get_all_locations(self):
        pass

    @abstractmethod
    def get_all_cases(self):
        pass

class CacheInterface(ABC):
    @abstractmethod
    def get(self, key):
        pass

    @abstractmethod
    def set(self, key, value, timeout):
        pass

    @abstractmethod
    def delete(self, key):
        pass
