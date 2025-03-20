from .interfaces import CaseRetrievalInterface, CaseRepositoryInterface, CacheInterface
from django.core.cache import cache
from .interfaces import CaseRepositoryInterface
from .formatters import CaseNewsDetailFormatter, CaseHealthProtocolDetailFormatter, CaseGenderDetailFormatter

class CaseService(CaseRetrievalInterface):
    CACHE_KEY = "all_case_locations"
    CACHE_TIMEOUT = 300 

    def __init__(self, repository: CaseRepositoryInterface, cache_service: CacheInterface):
        self.repository = repository
        self.cache_service = cache_service

    def get_all_case_locations(self):
        locations = self.cache_service.get(self.CACHE_KEY)
        if locations is None:
            locations = self.repository.get_all_locations()
            self.cache_service.set(self.CACHE_KEY, locations, timeout=self.CACHE_TIMEOUT)
        return locations if locations else []
    

class CacheService(CacheInterface):
    def get(self, key):
        return cache.get(key)

    def set(self, key, value, timeout):
        cache.set(key, value, timeout)

    def delete(self, key):
        cache.delete(key)


class CaseDetailService:
    def __init__(self, repository: CaseRepositoryInterface, cache_service: CacheInterface):
        self.repository = repository
        self.cache_service = cache_service

    def get_case_detail(self, case_id):
        cache_key = f"case_detail_{case_id}"
        cached_data = self.cache_service.get(cache_key)
        if cached_data:
            return cached_data

        case = self.repository.get_case_detail_by_id(case_id)
        if not case:
            return None

        try:
            case_data = {
                "id": case.id,
                "location": case.location.province if case.location else None,
                "gender": "Laki-laki" if case.gender == "Male" else "Perempuan",
                "age": case.age,
                "level_of_alertness": case.disease.level_of_alertness if case.disease else None,
                "related_search": f"https://www.google.com/search?q=Apa+itu+{case.disease.name.replace(' ', '+')}" if case.disease else None,
                "news": [
                    {
                        "img_url": news.img_url,
                        "url": news.url,
                        "date": news.date_published.strftime("%d %b %Y"),
                        "title": news.title,
                        "domain": news.url.split("/")[2] if news.url else ""
                    }
                    for news in case.news.all()
                ] if hasattr(case, 'news') else [],
                "health_protocols": [
                    {
                        "title": protocol.health_protocol.title,
                        "url": protocol.health_protocol.url
                    }
                    for protocol in case.disease.protocols.all()
                ] if case.disease else []
            }
            
            self.cache_service.set(cache_key, case_data, timeout=3600)
            return case_data
        except Exception as e:
            print(f"Error processing case detail: {str(e)}")
            raise