from pt_backend.models import Disease, Location, News
from django.core.exceptions import ObjectDoesNotExist
    
class DiseaseRepository:
    def get_all_diseases_name(self):
        try:
            diseases = Disease.get_all_diseases()
            if not diseases.exists():
                return []
            return [disease.name for disease in diseases]
        except ObjectDoesNotExist:
            return {"error": "Error retrieving diseases"}

class LocationRepository:
    def get_all_locations_name(self):
        try:
            locations = Location.get_all_locations()
            if not locations.exists():
                return []
            return [location.name for location in locations]
        except ObjectDoesNotExist:
            return {"error": "Error retrieving locations"}
        

class NewsRepository:
    def get_all_news_name(self):
        try:
            news = News.get_all_news()
            if not news.exists():
                return []
            return [news.portal for news in news]
        except ObjectDoesNotExist:
            return {"error": "Error retrieving news"}