from .interfaces import CaseRetrievalInterface, CaseRepositoryInterface, CacheInterface
from django.core.cache import cache

class CaseService(CaseRetrievalInterface):
    CACHE_KEY = "all_case_locations"
    CACHE_TIMEOUT = 300 

    def __init__(self, repository: CaseRepositoryInterface, cache_service: CacheInterface):
        self.repository = repository
        self.cache_service = cache_service
    
    def get_all_cases(self):
        cases = self.cache_service.get(self.CACHE_KEY_ALL_CASES)
        if cases is None:
            cases = self.repository.get_all_cases()
            self.cache_service.set(self.CACHE_KEY_ALL_CASES, cases, timeout=self.CACHE_TIMEOUT)
        return cases if cases else []

    def get_all_case_locations(self):
        locations = self.cache_service.get(self.CACHE_KEY)
        if locations is None:
            locations = self.repository.get_all_locations()
            self.cache_service.set(self.CACHE_KEY, locations, timeout=self.CACHE_TIMEOUT)
        return locations if locations else []
    
    def get_cases_by_year(self, year):
        cases = self.cache_service.get(self.CACHE_KEY_ALL_CASES)
        if cases is None:
            cases = self.repository.get_cases_by_year(year)
            self.cache_service.set(self.CACHE_KEY_ALL_CASES, cases, timeout=self.CACHE_TIMEOUT)
        return cases if cases else []

class CacheService(CacheInterface):
    def get(self, key):
        return cache.get(key)

    def set(self, key, value, timeout):
        cache.set(key, value, timeout)

    def delete(self, key):
        cache.delete(key)