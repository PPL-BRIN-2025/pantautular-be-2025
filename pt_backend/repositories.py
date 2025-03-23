from .models import Case, Disease, Location, News
from django.core.exceptions import ObjectDoesNotExist
from .interfaces import CaseRepositoryInterface
from django.utils import timezone
from django.db.models import Count
from datetime import datetime

class DiseaseRepository:
    def get_all_diseases_name(self):
        try:
            diseases = Disease.objects.values_list("name", flat=True).distinct()
            if not diseases.exists():
                return []
            return list(diseases)
        except ObjectDoesNotExist:
            return {"error": "Error retrieving diseases"}

class LocationRepository:
    def get_all_locations_name(self):
        try:
            locations = Location.objects.values_list("city", flat=True).distinct()
            if not locations.exists():
                return []
            return list(locations)
        except ObjectDoesNotExist:
            return {"error": "Error retrieving locations"}
        

class NewsRepository:
    def get_all_news_name(self):
        try:
            news = News.objects.values_list("portal", flat=True).distinct()
            if not news.exists():
                return []
            return list(news)
        except ObjectDoesNotExist:
            return {"error": "Error retrieving news"}

class CaseRepository(CaseRepositoryInterface):
    def get_all_locations(self):
        return Case.get_all_locations()
    def get_prevalence(self, year=None):
        POPULATION_DATA = {
            2019: 266911.9,
            2020: 270203.9,
            2021: 272682.5,
            2022: 275773.8,  
            2023: 278696.2,  
            2024: 281603.8,   
        }
        
        if year is None:
            year = 2024
            
        try:
            total_cases = Case.objects.filter(
                news__date_published__year=year
            ).distinct().count()
            
            population = POPULATION_DATA.get(year)
            if not population:
                return {"error": f"Population data not available for year {year}"}
            
            population = int(population * 1_000)  
            
            prevalence = (total_cases / population) * 100
            
            return {
                "year": year,
                "total_cases": total_cases,
                "population": population,
                "prevalence": prevalence
            }
            
        except Exception as e:
            return {"error": f"Error calculating prevalence: {str(e)}"}
