from .interfaces import CaseRetrievalInterface, CaseRepositoryInterface, CacheInterface
from django.core.cache import cache
from .interfaces import CaseRepositoryInterface
from .formatters import CaseNewsDetailFormatter, CaseHealthProtocolDetailFormatter, CaseGenderDetailFormatter
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer
from deep_translator import GoogleTranslator

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
    def __init__(
        self,
        repository: CaseRepositoryInterface,
        cache_service: CacheInterface,
        news_formatter: CaseNewsDetailFormatter,
        protocol_formatter: CaseHealthProtocolDetailFormatter,
        gender_formatter: CaseGenderDetailFormatter
    ):
        self.repository = repository
        self.cache_service = cache_service
        self.news_formatter = news_formatter
        self.protocol_formatter = protocol_formatter
        self.gender_formatter = gender_formatter


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
                "gender": self.gender_formatter.format(case.gender),
                "age": case.age,
                "level_of_alertness": case.disease.level_of_alertness if case.disease else None,
                "related_search": self._generate_related_search(case.disease.name) if case.disease else None,
                "news": self._format_news(case.news.all()) if hasattr(case, 'news') else [],
                "health_protocols": self._format_health_protocols(case.disease) if case.disease else [],
            }
            
            self.cache_service.set(cache_key, case_data, timeout=3600)
            return case_data
        except Exception as e:
            print(f"Error processing case detail: {str(e)}")
            raise


    def _format_news(self, news_queryset):
        try:
            news_list = list(news_queryset)
            return [self.news_formatter.format(news) for news in news_list]
        except Exception as e:
            print(f"Error formatting news: {str(e)}")
            return []


    def _format_health_protocols(self, disease):
        try:
            return [
                self.protocol_formatter.format(protocol_disease.health_protocol)
                for protocol_disease in disease.protocols.all()
            ]
        except Exception as e:
            print(f"Error formatting health protocols: {str(e)}")
            return []


    def _generate_related_search(self, disease_name):
        if not disease_name:
            return None
        query = disease_name.replace(" ", "+")
        return f"https://www.google.com/search?q=Apa+itu+{query}"
   