from .models import Case, Disease, Location, News
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Case
from .models import Case
from .interfaces import CaseRepositoryInterface

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
        
    def get_healthcare_news_statistics(self):
        try:
            news_stats = News.objects.filter(type="Kesehatan") \
                .values('portal') \
                .annotate(
                    news_count=Count('id'),
                    disease_count=Count('case__disease', distinct=True)
                )

            results = []
            for stat in news_stats:
                results.append({
                    'portal': stat['portal'],
                    'news_count': stat['news_count'], 
                    'disease_count': stat['disease_count']
                })
            return results

        except ObjectDoesNotExist:
            return {"error": "Error retrieving news statistics"}

    def get_top_healthcare_news_portal(self):
        try:
            news_stats = News.objects.filter(type="Kesehatan") \
                .values('portal') \
                .annotate(
                    news_count=Count('id')
                ) \
                .order_by('-news_count')[:5]

            if not news_stats:
                return []

            results = []
            for stat in news_stats:
                results.append({
                    'portal': stat['portal'],
                    'count': stat['news_count']
                })
            return results

        except ObjectDoesNotExist:
            return {"error": "Error retrieving news"}

class CaseRepository(CaseRepositoryInterface):
    def get_all_locations(self):
        return Case.get_all_locations()
    
    def get_gender_distribution(self):
        gender_counts = Case.objects.values('gender').annotate(count=Count('id'))
        distribution = {'male': 0, 'female': 0}
        for gender_count in gender_counts:
            if gender_count['gender'].lower() == 'male':
                distribution['male'] = gender_count['count']
            elif gender_count['gender'].lower() == 'female':
                distribution['female'] = gender_count['count']
        return distribution