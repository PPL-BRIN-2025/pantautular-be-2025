from django.utils import timezone
from .models import Case, Disease, Location, News
from django.core.exceptions import ObjectDoesNotExist
from .interfaces import CaseRepositoryInterface
from django.db.models import Count
from django.db.models.functions import TruncDate
from collections import defaultdict

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

    def get_all_severities_dates(self):
        try:
            date_counts = (
                News.objects
                .annotate(date=TruncDate('date_published'))
                .values('case__severity', 'date')
                .annotate(count=Count('id'))
                .order_by('case__severity', 'date')
            )

            result = defaultdict(list)
            for item in date_counts:
                severity_key = str(item['case__severity'])
                if severity_key and severity_key != 'None':
                    result[severity_key].append({
                        "date": item['date'].strftime('%Y-%m-%d'),
                        "count": item['count']
                    })

            return dict(result)
        except Exception as e:
            return {"error": str(e)}

class CaseRepository(CaseRepositoryInterface):
    def get_all_cases(self):
        return Case.objects.all().values(
            "id",
            "location__province",
            "location__city",
            "news__portal",
            "severity",
            "news__date_published",
            "gender",
            "age",
            "status",
            "disease__name",
            "disease__level_of_alertness",
            "news__type",
        )
    def get_all_locations(self):
        return Case.get_all_locations()
    
    def get_case_detail_by_id(self, case_id):
        try:
            return Case.objects.select_related(
                "disease",  
                "location" 
            ).prefetch_related(
                "news",  
                "disease__protocols__health_protocol"  
            ).only(
                'id', 'gender', 'age',
                'disease__name', 'disease__level_of_alertness',
                'location__province'
            ).get(id=case_id)
        except (Case.DoesNotExist, Exception) as e: 
            print(f"Error getting case detail: {str(e)}")  
            return None