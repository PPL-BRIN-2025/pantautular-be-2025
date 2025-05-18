from collections import defaultdict
import math
import numpy as np
from .interfaces import CaseRetrievalInterface, CaseRepositoryInterface, CacheInterface
from .repositories import CaseRepository, DiseaseRepository, LocationRepository, NewsRepository, ClimateRepository
from django.core.cache import cache
from .formatters import CaseNewsDetailFormatter, CaseHealthProtocolDetailFormatter, CaseGenderDetailFormatter
from .constants import PROVINCE_TO_CODE, CLIMATE_ERROR_INVALID_FORMAT, CLIMATE_ERROR_MISSING_PROVINCE, CLIMATE_ERROR_INVALID_VALUE

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.db.models import Q

class CaseService(CaseRetrievalInterface):
    CACHE_KEY_ALL_CASES = "all_cases"
    CACHE_KEY_ALL_LOCATIONS = "all_locations"
    CACHE_TIMEOUT = 300 
    CACHE_KEY_STATUS_PROVINCE = "status_province"

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
        locations = self.cache_service.get(self.CACHE_KEY_ALL_LOCATIONS) # pragma: no cover
        if locations is None: # pragma: no cover
            locations = self.repository.get_all_locations() # pragma: no cover  
            self.cache_service.set(self.CACHE_KEY_ALL_LOCATIONS, locations, timeout=self.CACHE_TIMEOUT) # pragma: no cover
        return locations if locations else [] # pragma: no cover
        
    def get_cases_by_year(self, year):
        cases = self.cache_service.get(self.CACHE_KEY_ALL_CASES)
        if cases is None:
            cases = self.repository.get_cases_by_year(year)
            self.cache_service.set(self.CACHE_KEY_ALL_CASES, cases, timeout=self.CACHE_TIMEOUT)
        return cases if cases else []
    
    def get_status_and_province(self):
        data = self.cache_service.get(self.CACHE_KEY_STATUS_PROVINCE)
        if data is None:
            repo_data = self.repository.get_status_and_province()
            data = list(repo_data) if repo_data else []
            self.cache_service.set(self.CACHE_KEY_STATUS_PROVINCE, data, timeout=self.CACHE_TIMEOUT)
        return data

class CacheService(CacheInterface):
    def get(self, key):
        return cache.get(key)

    def set(self, key, value, timeout):
        cache.set(key, value, timeout)

    def delete(self, key):
        cache.delete(key)

class DiseaseService:
    def __init__(self, repository=None):
        self.repository = repository or DiseaseRepository()
    
    def get_disease_severity_stats(self):
        print("Service: Fetching disease severity stats")
        result = self.repository.get_disease_severity_stats()
        print(f"Service: Received result type: {type(result)}")
        return result

class LocationService:
    def __init__(self, repository=None):
        self.repository = repository or LocationRepository()
        
    def get_province_severity_stats(self):
        result = self.repository.get_province_severity_stats()
        return result

    def get_city_severity_stats(self):
        result = self.repository.get_city_severity_stats()
        return result
    
class NewsService:
    def get_severities_dates(self):
        return NewsRepository().get_all_severities_dates()

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
   
class CasesFilterService:
    def __init__(self, case_service):
        self.case_service = case_service

    def filter_cases(self, disease=None, provinces=None, cities=None, portals=None, disease_alertness=None, date_range=None, ids_only = False):
        cases = self.case_service.get_all_cases()
        cases = self._filter_by_disease(cases, disease)
        cases = self._filter_by_locations(cases, provinces, cities)
        cases = self._filter_by_news_portals(cases, portals)
        cases = self._filter_by_disease_alertness(cases, disease_alertness)
        cases = self._filter_by_news_date_range(cases, date_range)

        if ids_only:
            return cases.values('id')
        return cases
    
    def _filter_by_disease(self, cases, disease):
        if disease:
            return cases.filter(disease__name__in=disease)
        return cases

    def _filter_by_locations(self, cases, provinces, cities):
        """Filter cases by provinces or cities."""
        if provinces and cities:
            # Menggunakan Q untuk OR antara provinces dan cities
            return cases.filter(
                Q(location__province__in=provinces) | Q(location__city__in=cities)
            )
        elif provinces:
            return cases.filter(location__province__in=provinces)
        elif cities:
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
        
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        elif isinstance(date_range, dict):
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

class SeverityFilteringService:
    def __init__(self):
        self.disease_repository = DiseaseRepository()
        self.location_repository = LocationRepository()
        self.filter_service = CasesFilterService(
            case_service=CaseService(
                repository=CaseRepository(), 
                cache_service=CacheService()
            )
        )
    
    def get_filter_stats(self, 
                          diseases=None, 
                          provinces=None, 
                          cities=None, 
                          news_portals=None, 
                          alert_levels=None, 
                          date_range=None):
        
        # Get filtered case IDs from filter service
        filtered_case_ids = self.filter_service.filter_cases(
            diseases, provinces, cities, news_portals, alert_levels, date_range, ids_only=True
        )
        
        # Get all three statistics using the same filtered case IDs
        return {
            "disease_stats": self.disease_repository.get_disease_severity_stats(filtered_case_ids),
            "province_stats": self.location_repository.get_province_severity_stats(filtered_case_ids),
            "city_stats": self.location_repository.get_city_severity_stats(filtered_case_ids)
        }

class ClimateService:
    CACHE_KEY_HUMIDITY = "province_humidity"
    CACHE_KEY_PRECIPITATION = "province_precipitation"
    CACHE_KEY_TEMPERATURE = "province_temperature"
    CACHE_TIMEOUT = 3600  # 1 jam dalam detik

    def __init__(self, repository=None, cache_service=None):
        self.repository = repository or ClimateRepository()
        self.cache_service = cache_service or CacheService()

    def _validate_data_format(self, data, field_name):
        if not data:
            return f"No {field_name} data available."
        
        if not isinstance(data, list):
            return CLIMATE_ERROR_INVALID_FORMAT
        
        return None

    def _validate_item_format(self, item):
        if not isinstance(item, dict):
            return CLIMATE_ERROR_INVALID_FORMAT
        
        if "province" not in item:
            return CLIMATE_ERROR_MISSING_PROVINCE
        
        if "value" not in item:
            return CLIMATE_ERROR_INVALID_FORMAT
        
        return None

    def _validate_province(self, province, seen_provinces):
        if not province:
            return CLIMATE_ERROR_MISSING_PROVINCE
        
        if province not in PROVINCE_TO_CODE:
            return f"Invalid province name: {province}"
        
        if province in seen_provinces:
            return f"Duplicate province found: {province}"
        
        seen_provinces.add(province)
        return None

    def _validate_value(self, value):
        if not isinstance(value, (int, float)):
            return CLIMATE_ERROR_INVALID_VALUE
        return None

    def _validate_climate_data(self, data, field_name):
        format_error = self._validate_data_format(data, field_name)
        if format_error:
            return format_error
        
        seen_provinces = set()
        for item in data:
            item_error = self._validate_item_format(item)
            if item_error:
                return item_error
            
            province_error = self._validate_province(item["province"], seen_provinces)
            if province_error:
                return province_error
            
            value_error = self._validate_value(item["value"])
            if value_error:
                return value_error
        
        return None

    def validate_humidity_data(self, data):
        return self._validate_climate_data(data, "humidity")

    def validate_precipitation_data(self, data):
        return self._validate_climate_data(data, "precipitation")

    def validate_temperature_data(self, data):
        return self._validate_climate_data(data, "temperature")

    def _get_province_climate_data(self, cache_key, field_name):
        try:
            # Try to get from cache first
            cached_data = self.cache_service.get(cache_key)
            if cached_data is not None:
                return cached_data

            # Get latest climate data for each province
            latest_climate = self.repository.get_latest_climate_data()
            
            # Format the data
            climate_data = []
            for climate in latest_climate:
                climate_data.append({
                    "province": climate.province,
                    "value": float(getattr(climate, field_name))
                })
            
            # Validate data first
            validation_error = getattr(self, f"validate_{field_name}_data")(climate_data)
            if validation_error:
                return {"error": validation_error}
            
            # Save to cache after validation
            self.cache_service.set(cache_key, climate_data, timeout=self.CACHE_TIMEOUT)
            
            return climate_data
        except Exception as e:
            print(f"Error in get_province_{field_name}: {str(e)}")
            return {"error": str(e)}

    def get_province_humidity(self):
        return self._get_province_climate_data(self.CACHE_KEY_HUMIDITY, "humidity")

    def get_province_precipitation(self):
        return self._get_province_climate_data(self.CACHE_KEY_PRECIPITATION, "precipitation")

    def get_province_temperature(self):
        return self._get_province_climate_data(self.CACHE_KEY_TEMPERATURE, "temperature")

class AverageSeverityByProvince:
    STATUS_ENCODING = {
        "minimal": 1,
        "biasa": 2,
        "bahaya": 3,
        "katastropik": 4
    }

    def __init__(self, case_service):
        self.case_service = case_service
        self.PROVINCE_TO_CODE = PROVINCE_TO_CODE

    def compute(self):
        """
        Hitung weighted severity score dan kategorisasi status untuk setiap provinsi.
        Output: list of dicts [{ "id": province_code, "value": float, "status": str }, ...]
        """
        data = self.case_service.get_status_and_province()
        province_scores = defaultdict(list)

        for record in data:
            status = record.get("status")
            province = record.get("location__province")

            if status and province:
                status = status.lower()
                if status in self.STATUS_ENCODING:
                    encoded = self.STATUS_ENCODING[status]
                    province_scores[province].append(encoded)

        if not province_scores:
            return []

        weighted_result = {}
        all_scores = []

        for province, scores in province_scores.items():
            avg = sum(scores) / len(scores)
            weight = math.log(len(scores) + 1)
            weighted_score = round(avg * weight, 2)
            weighted_result[province] = {"value": weighted_score}
            all_scores.append(weighted_score)

        # Hitung kuartil dinamis
        q1 = np.percentile(all_scores, 25)
        q2 = np.percentile(all_scores, 50)
        q3 = np.percentile(all_scores, 75)

        # Klasifikasi berdasarkan score
        for province, result in weighted_result.items():
            score = result["value"]
            if score <= q1:
                result["status"] = "minimal"
            elif score <= q2:
                result["status"] = "biasa"
            elif score <= q3:
                result["status"] = "bahaya"
            else:
                result["status"] = "katastropik"
                
            # Add province code
            result["id"] = self.PROVINCE_TO_CODE.get(province, province)

        # Convert dictionary to list format
        formatted_result = [
            {
                "id": data["id"],
                "value": data["value"],
                "status": data["status"]
            } for province, data in weighted_result.items()
        ]

        return formatted_result
