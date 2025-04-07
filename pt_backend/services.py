from .interfaces import CaseRetrievalInterface, CaseRepositoryInterface, CacheInterface
from django.core.cache import cache
from datetime import datetime

class CaseService(CaseRetrievalInterface):
    CACHE_KEY_ALL_CASES = "all_cases"
    CAHCE_KEY_ALL_CASES_LOCATIONS = "all_cases_locations"
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
        locations = self.cache_service.get(self.CAHCE_KEY_ALL_CASES_LOCATIONS)
        if locations is None:
            locations = self.repository.get_all_locations()
            self.cache_service.set(self.CAHCE_KEY_ALL_CASES_LOCATIONS, locations, timeout=self.CACHE_TIMEOUT)
        return locations if locations else []


class CacheService(CacheInterface):
    def get(self, key):
        return cache.get(key)

    def set(self, key, value, timeout):
        cache.set(key, value, timeout)

    def delete(self, key):
        cache.delete(key)


class CaseFilterService:
    def __init__(self, case_service):
        self.case_service = case_service

    def filter_cases(self, provinces=None, cities=None, news_portals=None, severities=None, news_date_range=None):
        cases = self.case_service.get_all_cases()
        cases = self._filter_by_provinces(cases, provinces)
        cases = self._filter_by_cities(cases, cities)
        cases = self._filter_by_news_portals(cases, news_portals)
        cases = self._filter_by_severities(cases, severities)
        cases = self._filter_by_news_date_range(cases, news_date_range)
        return cases

    def _filter_by_provinces(self, cases, provinces):
        if provinces:
            return cases.filter(location__province__in=provinces)
        return cases

    def _filter_by_cities(self, cases, cities):
        if cities:
            return cases.filter(location__city__in=cities)
        return cases

    def _filter_by_news_portals(self, cases, news_portals):
        if news_portals:
            return cases.filter(news__portal__in=news_portals)
        return cases

    def _filter_by_severities(self, cases, severities):
        if severities:
            return cases.filter(severity__in=severities)
        return cases

    def _filter_by_news_date_range(self, cases, news_date_range):
        if news_date_range and len(news_date_range) == 2:
            start_date, end_date = news_date_range
            # Convert string dates to datetime if necessary
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date)
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date)
            return cases.filter(news__date_published__range=(start_date, end_date))
        return cases