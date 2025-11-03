import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.http import require_http_methods
from authentication.permissions import IsTokenAuthenticated
from authentication.security import CustomJWTAuthentication
from pt_backend.models import Location
from .serializers import CaseLocationSerializer, DiseaseSeverityStatsSerializer, LocationSeverityStatsSerializer, ProvinceHumiditySerializer, ProvinceTemperatureSerializer, ProvincePrecipitationSerializer
from .services import AverageSeverityByProvince, CacheService, CaseService, CaseDetailService, DiseaseService, LocationService, CasesFilterService, SeverityFilteringService, ClimateService
from .filter.service import CaseFilterService, CaseFilterValidationError
from .repositories import CaseRepository, DiseaseRepository, LocationRepository, NewsRepository, ClimateRepository
from .authentication import APIKeyAuthentication
from django.http import Http404, JsonResponse
from .formatters import CaseNewsDetailFormatter, CaseHealthProtocolDetailFormatter, CaseGenderDetailFormatter
from .statistics.coordinator import StatisticsCoordinator
from .prome_metrics import (
    measure_time, count_calls,
    CASE_SEARCHED, API_RESPONSE_TIME, API_ERRORS,
    DISEASE_SEVERITY_RESPONSE_TIME, DISEASE_SEVERITY_REQUESTS, DISEASE_SEVERITY_DATA_COUNT, DISEASE_SEVERITY_ERRORS,
    LOCATION_SEVERITY_RESPONSE_TIME, LOCATION_SEVERITY_REQUESTS, LOCATION_SEVERITY_DATA_COUNT, LOCATION_SEVERITY_ERRORS,
    CITY_SEVERITY_RESPONSE_TIME, CITY_SEVERITY_REQUESTS, CITY_SEVERITY_DATA_COUNT, CITY_SEVERITY_ERRORS,
    DB_QUERY_TIME, API_REQUEST_SIZE, API_RESPONSE_SIZE,
    CACHE_HIT_RATE, API_SUCCESS, DB_ERRORS, REQUEST_COUNT, REQUEST_LATENCY, track_active_requests, track_data_count
)
from .constants import CLIMATE_ERROR_INVALID_FORMAT
from datetime import datetime
from django.db import connections
from django.db.utils import OperationalError

logger = logging.getLogger(__name__)

INTERNAL_SERVER_ERR_MSG = "An unexpected error occurred. Please try again later."
CACHE_TIMEOUT = 600
CACHE_KEY_PREFIX = "stats_report_"

class AllCaseLocationsView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    serializer_class = CaseLocationSerializer

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        cache_service = CacheService()
        repository = CaseRepository()
        self.service = CaseService(repository, cache_service)
        self.filter_service = CaseFilterService()

    def get(self, request):
        try:
            cases = self.service.get_all_case_locations()
            serialized_data = self.serializer_class(cases, many=True).data
            if not serialized_data:
                return Response({"error": "No case locations found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(serialized_data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({"error": INTERNAL_SERVER_ERR_MSG}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @measure_time(API_RESPONSE_TIME)
    @count_calls(CASE_SEARCHED)
    def post(self, request):
        try:
            if not request.data or all(not v for v in request.data.values()):
                cases = self.service.get_all_case_locations()
            else: 
                payload = self._prepare_filter_payload(request.data)
                cases = self.filter_service.filter_cases(payload)

            if not cases:
                return Response(
                    {"error": "No cases found with the given filters"},
                    status=status.HTTP_404_NOT_FOUND
                )

            serialized_data = self.serializer_class(cases, many=True).data
            return Response(
                serialized_data,
                status=status.HTTP_200_OK
            )
        except CaseFilterValidationError as err:
            return Response(err.as_payload(), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error in case filter: {str(e)}")
            API_ERRORS.labels(error_type='case_filter_error').inc()
            return Response(
                {"error": INTERNAL_SERVER_ERR_MSG},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _prepare_filter_payload(self, data):
        time_params = self.filter_service.parse_time_params(data)
        payload = self._flatten_request_data(data)
        if time_params:
            payload.update(time_params)
        return payload

    @staticmethod
    def _flatten_request_data(data):
        if hasattr(data, "lists"):
            flattened = {}
            for key, values in data.lists():
                if len(values) == 1:
                    flattened[key] = values[0]
                else:
                    flattened[key] = values
            return flattened
        if isinstance(data, dict):
            return {key: data[key] for key in data}
        return dict(data)

class FiltersView(APIView):
    def get(self, request):
        disease_repository = DiseaseRepository()
        location_repository = LocationRepository()
        news_repository = NewsRepository()
        try:
            diseases = [{"value": d, "label": d} for d in disease_repository.get_all_diseases_name()]
            provinces = [{"value": l, "label": l} for l in location_repository.get_all_locations_province()]
            cities = [{"value": l, "label": l} for l in location_repository.get_all_locations_city()]
            news = [{"value": n, "label": n} for n in news_repository.get_all_news_name()]


            response_data = {
                "data": {
                    "diseases": diseases,
                    "locations": {
                        "provinces": provinces,
                        "cities": cities
                    },
                    "news": news
                }
            }

            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)     

class DiseaseSeverityStatsView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    serializer_class = DiseaseSeverityStatsSerializer
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = DiseaseService()
    
    @measure_time(DISEASE_SEVERITY_RESPONSE_TIME)
    @count_calls(DISEASE_SEVERITY_REQUESTS)
    @track_data_count(DISEASE_SEVERITY_DATA_COUNT)
    @track_active_requests
    def get(self, request):
        try:
            stats = self.service.get_disease_severity_stats()
            
            if isinstance(stats, dict) and "error" in stats:
                DISEASE_SEVERITY_ERRORS.inc()
                API_ERRORS.labels(error_type="service_error", endpoint="disease_severity").inc()
                return Response(stats, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            serialized_data = self.serializer_class(stats, many=True).data
            API_SUCCESS.labels(endpoint="disease_severity").inc()
            return Response({
                "data": serialized_data
            }, status=status.HTTP_200_OK)
            
        except Exception:
            DISEASE_SEVERITY_ERRORS.inc()
            API_ERRORS.labels(error_type="exception", endpoint="disease_severity").inc()
            return Response(
                {"error": INTERNAL_SERVER_ERR_MSG},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class LocationSeverityStatsView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    serializer_class = LocationSeverityStatsSerializer
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        repository = LocationRepository()
        self.service = LocationService(repository=repository)
    
    @measure_time(LOCATION_SEVERITY_RESPONSE_TIME)
    @count_calls(LOCATION_SEVERITY_REQUESTS)
    @track_data_count(LOCATION_SEVERITY_DATA_COUNT)
    @track_active_requests
    def get(self, request):
        try:
            stats = self.service.get_province_severity_stats()
            
            if isinstance(stats, dict) and "error" in stats:
                LOCATION_SEVERITY_ERRORS.inc()
                API_ERRORS.labels(error_type="service_error", endpoint="location_severity").inc()
                return Response(stats, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            serialized_data = self.serializer_class(stats, many=True).data
            API_SUCCESS.labels(endpoint="location_severity").inc()
            return Response({
                "data": serialized_data
            }, status=status.HTTP_200_OK)
            
        except Exception:
            LOCATION_SEVERITY_ERRORS.inc()
            API_ERRORS.labels(error_type="exception", endpoint="location_severity").inc()
            return Response(
                {"error": INTERNAL_SERVER_ERR_MSG},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CitySeverityStatsView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    serializer_class = LocationSeverityStatsSerializer
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        repository = LocationRepository()
        self.service = LocationService(repository=repository)
    
    @measure_time(CITY_SEVERITY_RESPONSE_TIME)
    @count_calls(CITY_SEVERITY_REQUESTS)
    @track_data_count(CITY_SEVERITY_DATA_COUNT)
    @track_active_requests
    def get(self, request):
        try:
            stats = self.service.get_city_severity_stats()
            
            if isinstance(stats, dict) and "error" in stats:
                CITY_SEVERITY_ERRORS.inc()
                API_ERRORS.labels(error_type="service_error", endpoint="city_severity").inc()
                return Response(stats, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            serialized_data = self.serializer_class(stats, many=True).data
            API_SUCCESS.labels(endpoint="city_severity").inc()
            return Response({
                "data": serialized_data
            }, status=status.HTTP_200_OK)
            
        except Exception:
            CITY_SEVERITY_ERRORS.inc()
            API_ERRORS.labels(error_type="exception", endpoint="city_severity").inc()
            return Response(
                {"error": INTERNAL_SERVER_ERR_MSG},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class CaseDetailView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        repository = CaseRepository()
        cache_service = CacheService()
        self.case_service = CaseDetailService(
            repository=repository,
            cache_service=cache_service,
            news_formatter=CaseNewsDetailFormatter(),
            protocol_formatter=CaseHealthProtocolDetailFormatter(),
            gender_formatter=CaseGenderDetailFormatter()
        )

    def get(self, request, case_id):
        case_data = self.case_service.get_case_detail(case_id)
        if not case_data:
            raise Http404("Case not found")
        return Response(case_data)

class StatisticsView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Setup services
        cache_service = CacheService()
        case_repository = CaseRepository()
        
        case_service = CaseService(case_repository, cache_service)
        case_filter_service = CasesFilterService(case_service)
        
        # Create coordinator
        self.statistics_coordinator = StatisticsCoordinator(
            case_filter_service=case_filter_service
        )
    
    def get(self, request):
        """Get all statistics without applying any filters"""
        try:
            # Generate comprehensive report without filters
            statistics = self.statistics_coordinator.generate_comprehensive_report()
            
            return Response(statistics, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(e)
            return Response(
                {"error": "An error occurred while fetching statistics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        try:
            filter_params = self._get_filter_params(request)

            # Generate comprehensive report with processed filters
            statistics = self.statistics_coordinator.generate_comprehensive_report(**filter_params)
            
            return Response(statistics, status=status.HTTP_200_OK)
            
        except CaseFilterValidationError as err:
            return Response(err.as_payload(), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response(
                {"error": "An error occurred while fetching statistics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_filter_params(self, request):
        filter_params = {}
        
        # Handle diseases
        self._add_diseases(request, filter_params)
        
        # Handle locations
        self._add_locations(request, filter_params)
        
        # Handle portals
        self._add_portals(request, filter_params)
        
        # Handle alertness level
        self._add_alertness(request, filter_params)
        
        # Handle date range
        self._add_date_range(request, filter_params)
        
        return filter_params

    def _add_diseases(self, request, filter_params):
        if 'diseases' in request.data and request.data['diseases']:
            filter_params['disease'] = request.data['diseases']

    def _add_locations(self, request, filter_params):
        if 'locations' in request.data and request.data['locations']:
            if 'provinces' in request.data['locations'] and request.data['locations']['provinces']:
                filter_params['provinces'] = request.data['locations']['provinces']
            if 'cities' in request.data['locations'] and request.data['locations']['cities']:
                filter_params['cities'] = request.data['locations']['cities']

    def _add_portals(self, request, filter_params):
        if 'portals' in request.data and request.data['portals']:
            filter_params['portals'] = request.data['portals']

    def _add_alertness(self, request, filter_params):
        if 'level_of_alertness' in request.data and request.data['level_of_alertness'] is not None:
            alertness = int(request.data['level_of_alertness'])
            if alertness > 0:
                filter_params['disease_alertness'] = alertness

    def _add_date_range(self, request, filter_params):
        time_range = CaseFilterService.parse_time_range(
            request.data,
            return_type="dict",
        )
        if time_range:
            filter_params['date_range'] = time_range

    
class SeverityFilteringStatsView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache_service = CacheService()
        self.cache_timeout = CACHE_TIMEOUT
    
    def post(self, request):
        """Handle POST requests with JSON payload for filtering"""
        try:
            # Extract and process filter parameters
            filter_params = self._extract_filter_parameters(request.data)
            
            # Generate cache key based on filter parameters
            cached_results = self._generate_cache_key(filter_params)
            cache_key = getattr(self, "_current_cache_key", None)

            if cached_results is not None:
                return Response(cached_results, status=status.HTTP_200_OK)

            if cache_key is None:
                raise ValueError("Unable to generate cache key")
            
            # Initialize service and get results if not in cache
            severity_filter = SeverityFilteringService()
            results = severity_filter.get_filter_stats(**filter_params)
            
            # Cache the results
            self.cache_service.set(cache_key, results, timeout=self.cache_timeout)
            
            return Response(results, status=status.HTTP_200_OK)
        
        except CaseFilterValidationError as err:
            return Response(err.as_payload(), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Error processing filter request: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _generate_cache_key(self, filter_params):
        try:
            hashable_items = []
            for key, value in filter_params.items():
                normalized = self._normalize_cache_value(value)
                hashable_items.append((key, normalized))
            cache_key = f"{CACHE_KEY_PREFIX}{hash(frozenset(hashable_items))}"
            self._current_cache_key = cache_key
            return self.cache_service.get(cache_key)
        except Exception as e:
            logger.error(f"Cache key generation error: {str(e)}")
            self._current_cache_key = None
            raise

    @staticmethod
    def _normalize_cache_value(value):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return tuple(
                (k, SeverityFilteringStatsView._normalize_cache_value(v))
                for k, v in sorted(value.items())
            )
        if isinstance(value, (list, tuple, set)):
            return tuple(
                SeverityFilteringStatsView._normalize_cache_value(v)
                for v in value
            )
        return value

    
    def _extract_filter_parameters(self, data):
        """Extract and process filter parameters from request data"""
        # Extract basic filters
        diseases = data.get('diseases', []) or None
        locations = data.get('locations', {})
        portals = data.get('portals', []) or None
        
        # Process location data
        provinces, cities = self._process_location_data(locations)
        
        # Process alertness level
        level_of_alertness = data.get('level_of_alertness') or None
        if level_of_alertness:
            level_of_alertness = int(level_of_alertness)
        
        time_window = CaseFilterService.parse_time_range(
            data,
            return_type="tuple",
        )
        date_range = time_window if time_window else None
        
        return {
            'diseases': diseases,
            'provinces': provinces,
            'cities': cities,
            'news_portals': portals,
            'alert_levels': level_of_alertness,
            'date_range': date_range
        }
    
    def _process_location_data(self, locations):
        """Process location data to extract provinces and cities"""
        if not locations:
            return None, None

        provinces = []
        cities = []

        # Process provinces
        if locations.get('provinces', []):
            for province in locations.get('provinces', []):
                if Location.objects.filter(province=province).exists():
                    provinces.append(province)

        # Process cities
        if locations.get('cities', []):
            for city in locations.get('cities', []):
                if Location.objects.filter(city=city).exists():
                    cities.append(city)

        # Ensure that cities are unique
        cities = list(set(cities)) if cities else None

        # Clean up results
        provinces = list(set(provinces)) if provinces else None

        return provinces, cities



class ProvinceHumidityView(APIView):
    authentication_classes = [CustomJWTAuthentication, APIKeyAuthentication]
    permission_classes = [IsTokenAuthenticated]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache_service = CacheService()
        self.climate_service = ClimateService(repository=ClimateRepository(), cache_service=self.cache_service)
    
    def get(self, request):
        try:
            data = self.climate_service.get_province_humidity()
            
            if isinstance(data, dict) and "error" in data:
                error_msg = data["error"]
                if any(msg in error_msg for msg in ["Invalid", "No", "Duplicate"]):
                    return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)
                return Response({"error": error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            if not data:
                return Response({"error": "No humidity data available."}, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = ProvinceHumiditySerializer(data=data, many=True)
            if not serializer.is_valid():
                return Response({"error": CLIMATE_ERROR_INVALID_FORMAT}, status=status.HTTP_400_BAD_REQUEST)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProvincePrecipitationView(APIView):
    authentication_classes = [CustomJWTAuthentication, APIKeyAuthentication]
    permission_classes = [IsTokenAuthenticated]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache_service = CacheService()
        self.climate_service = ClimateService(repository=ClimateRepository(), cache_service=self.cache_service)
    
    def get(self, request):
        try:
            data = self.climate_service.get_province_precipitation()
            
            if isinstance(data, dict) and "error" in data:
                error_msg = data["error"]
                if any(msg in error_msg for msg in ["Invalid", "No", "Duplicate"]):
                    return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)
                return Response({"error": error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            if not data:
                return Response({"error": "No precipitation data available."}, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = ProvincePrecipitationSerializer(data=data, many=True)
            if not serializer.is_valid():
                return Response({"error": CLIMATE_ERROR_INVALID_FORMAT}, status=status.HTTP_400_BAD_REQUEST)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProvinceTemperatureView(APIView):
    authentication_classes = [CustomJWTAuthentication, APIKeyAuthentication]
    permission_classes = [IsTokenAuthenticated]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache_service = CacheService()
        self.climate_service = ClimateService(repository=ClimateRepository(), cache_service=self.cache_service)
    
    def get(self, request):
        try:
            data = self.climate_service.get_province_temperature()
            
            if isinstance(data, dict) and "error" in data:
                error_msg = data["error"]
                if any(msg in error_msg for msg in ["Invalid", "No", "Duplicate"]):
                    return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)
                return Response({"error": error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            if not data:
                return Response({"error": "No temperature data available."}, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = ProvinceTemperatureSerializer(data=data, many=True)
            if not serializer.is_valid():
                return Response({"error": CLIMATE_ERROR_INVALID_FORMAT}, status=status.HTTP_400_BAD_REQUEST)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class WeightedSeverityAnalysisView(APIView):
    authentication_classes = [CustomJWTAuthentication, APIKeyAuthentication]
    permission_classes = [IsTokenAuthenticated]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.case_service = CaseService(
            repository=CaseRepository(),
            cache_service=CacheService()
        )
        self.severity_analyzer = AverageSeverityByProvince(self.case_service)
    
    def get(self, request):
        try:
            result = self.severity_analyzer.compute()
            
            if not result:
                return Response(
                    {"error": "No case data available"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception:
            return Response(
                {"error": INTERNAL_SERVER_ERR_MSG},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@require_http_methods(['GET'])
def health_check(request):
    """
    Health check endpoint for Docker container
    """
    # Check database connection
    db_healthy = True
    try:
        connections['default'].cursor()
    except OperationalError:
        db_healthy = False
    
    status = 200 if db_healthy else 500
    
    health_data = {
        'status': 'healthy' if db_healthy else 'unhealthy',
        'database': 'connected' if db_healthy else 'disconnected',
        'timestamp': datetime.now().isoformat()
    }
    
    return JsonResponse(health_data, status=status)
