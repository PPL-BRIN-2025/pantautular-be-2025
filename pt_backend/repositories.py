from .models import Case, Disease, Location, News
from django.core.exceptions import ObjectDoesNotExist
from .models import Case
from .interfaces import CaseRepositoryInterface

class DiseaseRepository:
    def get_all_diseases_name(self):
        try:
            diseases = Disease.objects.all()
            if not diseases.exists():
                return []
            return [disease.name for disease in diseases]
        except ObjectDoesNotExist:
            return {"error": "Error retrieving diseases"}

class LocationRepository:
    def get_all_locations_name(self):
        try:
            locations = Location.objects.all()
            if not locations.exists():
                return []
            return [location.name for location in locations]
        except ObjectDoesNotExist:
            return {"error": "Error retrieving locations"}
        

class NewsRepository:
    def get_all_news_name(self):
        try:
            news = News.objects.all()
            if not news.exists():
                return []
            return [news.portal for news in news]
        except ObjectDoesNotExist:
            return {"error": "Error retrieving news"}

class CaseRepository(CaseRepositoryInterface):
    def get_all_locations(self):
        return Case.get_all_locations()
