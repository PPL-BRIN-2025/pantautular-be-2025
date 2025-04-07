from .interfaces import CaseRetrievalInterface, CaseRepositoryInterface, CacheInterface
from django.core.cache import cache
from datetime import datetime

class CaseService(CaseRetrievalInterface):
    CACHE_KEY_ALL_CASES = "all_cases"
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
    
    def get_gender_dist(self):
        return self.repository.get_gender_distribution()

class CacheService(CacheInterface):
    def get(self, key):
        return cache.get(key)

    def set(self, key, value, timeout):
        cache.set(key, value, timeout)

    def delete(self, key):
        cache.delete(key)


class CasesFilterService:
    def __init__(self, case_service):
        self.case_service = case_service

    def filter_cases(self, disease=None, provinces=None, cities=None, portals=None, level_of_alertness=None, date_range=None):
        cases = self.case_service.get_all_cases()
        cases = self._filter_by_disease(cases, disease)
        cases = self._filter_by_provinces(cases, provinces)
        cases = self._filter_by_cities(cases, cities)
        cases = self._filter_by_news_portals(cases, portals)
        cases = self._filter_by_disease_alertness(cases, level_of_alertness)
        cases = self._filter_by_news_date_range(cases, date_range)
        return cases
    
    def _filter_by_disease(self, cases, disease):
        if disease:
            return cases.filter(disease__name__in=disease)
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

    def _filter_by_disease_alertness(self, cases, alertness):
        if alertness:
            return cases.filter(disease__level_of_alertness=alertness)
        return cases

    def _filter_by_news_date_range(self, cases, date_range):
        if not date_range:
            return cases
        
        start_date = date_range.get('start')
        end_date = date_range.get('end')
        
        if start_date and end_date:
            # Both dates provided
            return cases.filter(news__date_published__range=[start_date, end_date])
        elif start_date:
            # Only start date provided
            return cases.filter(news__date_published__gte=start_date)
        elif end_date:
            # Only end date provided
            return cases.filter(news__date_published__lte=end_date)
        
        return cases