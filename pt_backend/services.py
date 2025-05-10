from .interfaces import CaseRetrievalInterface, CaseRepositoryInterface, CacheInterface
from .repositories import CaseRepository, DiseaseRepository, LocationRepository, NewsRepository, ClimateRepository
from django.core.cache import cache
from .formatters import CaseNewsDetailFormatter, CaseHealthProtocolDetailFormatter, CaseGenderDetailFormatter

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail

from .serializers import PROVINCE_TO_CODE

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
        locations = self.cache_service.get(self.CACHE_KEY_ALL_LOCATIONS)
        if locations is None:
            locations = self.repository.get_all_locations()
            self.cache_service.set(self.CACHE_KEY_ALL_LOCATIONS, locations, timeout=self.CACHE_TIMEOUT)
        return locations if locations else []
        
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
        cases = self._filter_by_provinces(cases, provinces)
        cases = self._filter_by_cities(cases, cities)
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

    def _filter_by_provinces(self, cases, provinces):
        if provinces:
            return cases.filter(location__province__in=provinces)
        return cases

    def _filter_by_cities(self, cases, cities):
        if cities:
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

    def validate_humidity_data(self, data):
        if not data:
            return "No humidity data available."
        
        if not isinstance(data, list):
            return "Invalid data format"
        
        seen_provinces = set()
        for item in data:
            if not isinstance(item, dict):
                return "Invalid data format"
            
            if "province" not in item:
                return "Missing province field"
            
            province = item["province"]
            if not province:
                return "Missing province field"
            
            if province not in PROVINCE_TO_CODE:
                return f"Invalid province name: {province}"
            
            if province in seen_provinces:
                return f"Duplicate province found: {province}"
            seen_provinces.add(province)
            
            if "value" not in item:
                return "Invalid data format"
            
            value = item["value"]
            if not isinstance(value, (int, float)):
                return "Invalid value type"
        
        return None

    def validate_precipitation_data(self, data):
        """Validate precipitation data"""
        if not data:
            return "No precipitation data available."
        
        if not isinstance(data, list):
            return "Invalid data format"
        
        seen_provinces = set()
        for item in data:
            if not isinstance(item, dict):
                return "Invalid data format"
            
            if "province" not in item:
                return "Missing province field"
            
            province = item["province"]
            if not province:
                return "Missing province field"
            
            if province not in PROVINCE_TO_CODE:
                return f"Invalid province name: {province}"
            
            if province in seen_provinces:
                return f"Duplicate province found: {province}"
            seen_provinces.add(province)
            
            if "value" not in item:
                return "Invalid data format"
            
            value = item["value"]
            if not isinstance(value, (int, float)):
                return "Invalid value type"
        
        return None

    def validate_temperature_data(self, data):
        if not data:
            return "No temperature data available."
        
        if not isinstance(data, list):
            return "Invalid data format"
        
        seen_provinces = set()
        for item in data:
            if not isinstance(item, dict):
                return "Invalid data format"
            
            if "province" not in item:
                return "Missing province field"
            
            province = item["province"]
            if not province:
                return "Missing province field"
            
            if province not in PROVINCE_TO_CODE:
                return f"Invalid province name: {province}"
            
            if province in seen_provinces:
                return f"Duplicate province found: {province}"
            seen_provinces.add(province)
            
            if "value" not in item:
                return "Invalid data format"
            
            value = item["value"]
            if not isinstance(value, (int, float)):
                return "Invalid value type"
        
        return None

    def get_province_humidity(self):
        try:
            # Try to get from cache first
            cached_data = self.cache_service.get(self.CACHE_KEY_HUMIDITY)
            if cached_data is not None:
                return cached_data

            # Get latest climate data for each province
            latest_climate = self.repository.get_latest_climate_data()
            
            # Format the data
            humidity_data = []
            for climate in latest_climate:
                humidity_data.append({
                    "province": climate.province,
                    "value": float(climate.humidity)
                })
            
            # Validate data first
            validation_error = self.validate_humidity_data(humidity_data)
            if validation_error:
                return {"error": validation_error}
            
            # Save to cache after validation
            self.cache_service.set(self.CACHE_KEY_HUMIDITY, humidity_data, timeout=self.CACHE_TIMEOUT)
            
            return humidity_data
        except Exception as e:
            print(f"Error in get_province_humidity: {str(e)}")
            return {"error": str(e)}

    def get_province_precipitation(self):
        try:
            # Try to get from cache first
            cached_data = self.cache_service.get(self.CACHE_KEY_PRECIPITATION)
            if cached_data is not None:
                return cached_data

            # Get latest climate data for each province
            latest_climate = self.repository.get_latest_climate_data()
            
            # Format the data
            precipitation_data = []
            for climate in latest_climate:
                precipitation_data.append({
                    "province": climate.province,
                    "value": float(climate.precipitation)
                })
            
            # Validate data first
            validation_error = self.validate_precipitation_data(precipitation_data)
            if validation_error:
                return {"error": validation_error}
            
            # Save to cache after validation
            self.cache_service.set(self.CACHE_KEY_PRECIPITATION, precipitation_data, timeout=self.CACHE_TIMEOUT)
            
            return precipitation_data
        except Exception as e:
            print(f"Error in get_province_precipitation: {str(e)}")
            return {"error": str(e)}

    def get_province_temperature(self):
        try:
            # Try to get from cache first
            cached_data = self.cache_service.get(self.CACHE_KEY_TEMPERATURE)
            if cached_data is not None:
                return cached_data

            # Get latest climate data for each province
            latest_climate = self.repository.get_latest_climate_data()
            
            # Format the data
            temperature_data = []
            for climate in latest_climate:
                temperature_data.append({
                    "province": climate.province,
                    "value": float(climate.temperature)
                })
            
            # Validate data first
            validation_error = self.validate_temperature_data(temperature_data)
            if validation_error:
                return {"error": validation_error}
            
            # Save to cache after validation
            self.cache_service.set(self.CACHE_KEY_TEMPERATURE, temperature_data, timeout=self.CACHE_TIMEOUT)
            
            return temperature_data
        except Exception as e:
            print(f"Error in get_province_temperature: {str(e)}")
            return {"error": str(e)}
