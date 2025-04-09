from .models import Case, Disease, Location, News
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, When, IntegerField, Sum, F, Q
from django.db.models import Case as DjangoCase  # Rename Django's Case to DjangoCase
from django.db.models.functions import Coalesce
from .interfaces import CaseRepositoryInterface
from django.db.models import Count
from django.db.models.functions import TruncDate
from collections import defaultdict

def get_entity_severity_stats(model_class, group_by_field=None, name_field=None, error_prefix="Error retrieving", limit=12):
    """
    Generic helper to get severity statistics for any entity.
    
    Args:
        model_class: The model class to query (Disease or Location).
        group_by_field: Field to group by (None for Disease, 'province' or 'city' for Location).
        name_field: Field to use as the name in results (defaults to group_by_field).
        error_prefix: Prefix for error messages.
        limit: Max number of results to return.
        
    Returns:
        List of dictionaries with severity stats or error dict.
    """
    try:
        if group_by_field:
            query = model_class.objects.values(group_by_field)
            is_values_query = True
            name_field = name_field or group_by_field
        else:
            query = model_class.objects
            is_values_query = False
            
        entities = query.annotate(
            hospitalisasi_count=Coalesce(
                Sum(
                    DjangoCase(
                        When(cases__severity__iexact='hospitalisasi', then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                ), 0
            ),
            insiden_count=Coalesce(
                Sum(
                    DjangoCase(
                        When(cases__severity__iexact='insiden', then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                ), 0
            ),
            mortalitas_count=Coalesce(
                Sum(
                    DjangoCase(
                        When(cases__severity__iexact='mortalitas', then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                ), 0
            ),
            total_cases=Coalesce(Count('cases', distinct=True), 0)
        ).order_by('-total_cases')[:limit] 

        result = []
        for entity in entities:
            if is_values_query:
                entity_name = entity[name_field]
                hospitalisasi = entity['hospitalisasi_count']
                insiden = entity['insiden_count']
                mortalitas = entity['mortalitas_count']
                total = entity['total_cases']
            else:
                entity_name = getattr(entity, name_field)
                hospitalisasi = entity.hospitalisasi_count
                insiden = entity.insiden_count
                mortalitas = entity.mortalitas_count
                total = entity.total_cases
                
            entity_info = {
                "name": entity_name,
                "severity_counts": {
                    "hospitalisasi": hospitalisasi or 0,
                    "insiden": insiden or 0,
                    "mortalitas": mortalitas or 0,
                },
                "total_cases": total or 0,
            }
            result.append(entity_info)
            
        return result
    except Exception as e:
        print(f"Error in get_entity_severity_stats: {e}")
        return {"error": f"{error_prefix} severity statistics"}

class DiseaseRepository:
    def get_all_diseases_name(self):
        try:
            diseases = Disease.objects.values_list("name", flat=True).distinct()
            if not diseases.exists():
                return []
            return list(diseases)
        except ObjectDoesNotExist:
            return {"error": "Error retrieving diseases"}
    
    def get_disease_severity_stats(self):
        return get_entity_severity_stats(
            model_class=Disease,
            group_by_field=None,
            name_field="name",
            error_prefix="Error retrieving disease"
        )

class LocationRepository:
    def get_all_locations_name(self):
        try:
            locations = Location.objects.values_list("city", flat=True).distinct()
            if not locations.exists():
                return []
            return list(locations)
        except ObjectDoesNotExist:
            return {"error": "Error retrieving locations"}
    
    def get_province_severity_stats(self):
        return get_entity_severity_stats(
            model_class=Location,
            group_by_field="province",
            error_prefix="Error retrieving province"
        )
    
    def get_city_severity_stats(self):
        return get_entity_severity_stats(
            model_class=Location, 
            group_by_field="city",
            error_prefix="Error retrieving city"
        )


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
        
    def get_cases_by_year(self, year):
        return Case.objects.filter(
            news__date_published__year=year
        ).distinct()
        
