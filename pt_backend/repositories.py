from .models import Case, Disease, Location, News
from django.core.exceptions import ObjectDoesNotExist

class CaseRepository:
    def get_all_case_locations(self):
        try:
            locations = Case.get_all_cases_locations()
            if not locations.exists():
                return []
            return [
                {
                    "id": str(location.case.id),
                    "city": location.case.city,
                    "latitude": f"{float(location.latitude):.6f}",
                    "longitude": f"{float(location.longitude):.6f}",
                }
                for location in locations
            ]
        except ObjectDoesNotExist:  
            return {"error": "Error retrieving case locations"}

    
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