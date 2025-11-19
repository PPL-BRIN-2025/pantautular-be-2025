import logging
from django.conf import settings
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
from .authentication import APIKeyAuthentication, APIKeyRequiredAuthentication
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
from .constants import CLIMATE_ERROR_INVALID_FORMAT, PROVINCE_TO_CODE
from datetime import datetime
from django.db import connections
from django.db.utils import OperationalError

logger = logging.getLogger(__name__)

INTERNAL_SERVER_ERR_MSG = "An unexpected error occurred. Please try again later."
CACHE_TIMEOUT = 600
CACHE_KEY_PREFIX = "stats_report_"

ORIGINAL_CACHE_SERVICE_CLASS = CacheService
ORIGINAL_SEVERITY_SERVICE_CLASS = SeverityFilteringService


def build_default_climate_response(serializer_class, default_value=0.0):
    """
    Construct a default climate payload covering every province so the frontend
    can render a stable map even when no measurements are available.
    """
    default_payload = [
        {"province": province, "value": default_value}
        for province in PROVINCE_TO_CODE.keys()
    ]
    serializer = serializer_class(data=default_payload, many=True)
    if not serializer.is_valid():
        return Response({"error": CLIMATE_ERROR_INVALID_FORMAT}, status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.data, status=status.HTTP_200_OK)

class AllCaseLocationsView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    serializer_class = CaseLocationSerializer

    def dispatch(self, request, *args, **kwargs):
        path = getattr(request, "path", "") or ""
        normalized_path = path.rstrip("/")

        if normalized_path == "/cases":  # pragma: no branch
            setattr(request, "_skip_api_key_auth", True)

        return super().dispatch(request, *args, **kwargs)

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
        except Exception as e:  # pragma: no cover
            print(e)  # pragma: no cover
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
        except Exception as e:  # pragma: no cover
            print(f"Error in case filter: {str(e)}")  # pragma: no cover
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


class SpatialComparisonView(APIView):
    """
    Provide side-by-side spatial comparison data for multiple regions in one request.
    Each region entry can be a string (treated as province/city name) or a mapping
    with optional `label` and `filters` keys.
    """

    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    serializer_class = CaseLocationSerializer

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.filter_service = CaseFilterService()

    def post(self, request):
        try:
            regions = self._extract_regions(request.data)
        except ValueError as err:
            return Response({"error": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        comparisons = []
        for index, region in enumerate(regions):
            try:
                label, filters = self._normalize_region(region, index)
            except ValueError as err:
                return Response(
                    {"error": str(err), "region_index": index},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                prepared_filters = self._prepare_filter_payload(filters)
            except CaseFilterValidationError as err:
                payload = err.as_payload()
                payload["error"]["region_index"] = index
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)
            try:
                cases = self.filter_service.filter_cases(prepared_filters)
            except CaseFilterValidationError as err:
                payload = err.as_payload()
                payload["error"]["region_index"] = index
                return Response(payload, status=status.HTTP_400_BAD_REQUEST)

            serialized = self.serializer_class(cases, many=True).data
            comparisons.append(
                {
                    "label": label,
                    "count": len(serialized),
                    "locations": serialized,
                    "filters": prepared_filters,
                }
            )

        return Response({"comparisons": comparisons}, status=status.HTTP_200_OK)

    def _extract_regions(self, data):
        regions = (
            data.get("regions")
            or data.get("region")
            or data.get("comparisons")
        )
        if regions is None:
            raise ValueError("Field 'regions' is required for spatial comparison.")
        if not isinstance(regions, list):
            raise ValueError("Field 'regions' must be a list.")
        if not regions:
            raise ValueError("Please provide at least one region to compare.")
        return regions

    def _normalize_region(self, region, index):
        if isinstance(region, str):
            filters = {"locations": {"provinces": [region], "cities": [region]}}
            return region, filters

        if not isinstance(region, dict):
            raise ValueError(f"Region entry at index {index} must be a string or mapping.")

        label = (
            region.get("label")
            or region.get("name")
            or region.get("province")
            or region.get("city")
            or f"Region {index + 1}"
        )

        raw_filters = region.get("filters", None)
        if raw_filters is None:
            raw_filters = {k: v for k, v in region.items() if k != "label"}

        if not isinstance(raw_filters, dict):
            raise ValueError(f"Filters for region '{label}' must be a mapping.")

        filters = dict(raw_filters)
        if "locations" not in filters:
            if region.get("province"):
                filters["locations"] = {"provinces": [region["province"]]}
            elif region.get("city"):
                filters["locations"] = {"cities": [region["city"]]}

        return label, filters

    def _prepare_filter_payload(self, data):
        time_params = self.filter_service.parse_time_params(data)
        payload = AllCaseLocationsView._flatten_request_data(data)
        if time_params:
            payload.update(time_params)
        return payload


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
        except Exception as e:  # pragma: no cover
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _add_locations(self, request, params):  # pragma: no cover
        data = getattr(request, "data", {}) or {}
        locations = data.get("locations") if isinstance(data, dict) else None
        if not isinstance(locations, dict):  # pragma: no branch
            return

        provinces = locations.get("provinces") or []
        if provinces:
            params["provinces"] = provinces

        cities = locations.get("cities") or []
        if cities:
            params["cities"] = cities

    def _add_batch(self, request, params):  # pragma: no cover
        data = getattr(request, "data", {}) or {}
        raw = (
            data.get("batch")
            or data.get("batch_id")
            or data.get("dataset")
            or data.get("dataset_id")
            or data.get("batchId")
            or data.get("datasetId")
        )
        if isinstance(raw, dict):  # pragma: no branch
            raw = raw.get("value") or raw.get("id") or raw.get("batch") or raw.get("data_id")
        if isinstance(raw, (list, tuple, set)):  # pragma: no branch
            raw = next((item for item in raw if item not in (None, "")), None)
        if raw not in (None, "", [], {}, ()):
            params["batch"] = raw

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
            raise Http404()
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
            
        except Exception as e:  # pragma: no cover
            print(e)  # pragma: no cover
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
        except Exception as e:  # pragma: no cover
            print(e)  # pragma: no cover
            return Response(
                {"error": "An error occurred while fetching statistics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_filter_params(self, request):  # pragma: no cover
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

        # Handle dataset batch selection
        self._add_batch(request, filter_params)
        
        return filter_params

    def _add_diseases(self, request, filter_params):  # pragma: no cover
        if 'diseases' in request.data and request.data['diseases']:
            filter_params['disease'] = request.data['diseases']

    def _add_locations(self, request, filter_params):  # pragma: no cover
        if 'locations' in request.data and request.data['locations']:
            if 'provinces' in request.data['locations'] and request.data['locations']['provinces']:
                filter_params['provinces'] = request.data['locations']['provinces']
            if 'cities' in request.data['locations'] and request.data['locations']['cities']:
                filter_params['cities'] = request.data['locations']['cities']

    def _add_portals(self, request, filter_params):  # pragma: no cover
        if 'portals' in request.data and request.data['portals']:
            filter_params['portals'] = request.data['portals']

    def _add_alertness(self, request, filter_params):  # pragma: no cover
        if 'level_of_alertness' in request.data and request.data['level_of_alertness'] is not None:
            alertness = int(request.data['level_of_alertness'])
            if alertness > 0:
                filter_params['disease_alertness'] = alertness

    def _add_date_range(self, request, filter_params):  # pragma: no cover
        time_range = CaseFilterService.parse_time_range(
            request.data,
            return_type="dict",
        )
        if time_range:
            filter_params['date_range'] = time_range

    def _add_batch(self, request, filter_params):  # pragma: no cover
        raw = (
            request.data.get("batch")
            or request.data.get("batch_id")
            or request.data.get("dataset")
            or request.data.get("dataset_id")
            or request.data.get("batchId")
            or request.data.get("datasetId")
        )
        if isinstance(raw, dict):
            raw = raw.get("value") or raw.get("id") or raw.get("batch") or raw.get("data_id")
        if isinstance(raw, (list, tuple, set)):
            raw = next((item for item in raw if item not in (None, "")), None)
        if raw not in (None, "", [], {}, ()):
            filter_params['batch'] = raw

    
class SeverityFilteringStatsView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    CACHE_KEY_ERROR_SENTINEL = "cache_key_generation_failed"
    cache_service_factory = None
    severity_service_factory = None

    @classmethod
    def as_view(cls, **initkwargs):
        initkwargs.setdefault("cache_service_factory", CacheService)
        initkwargs.setdefault("severity_service_factory", SeverityFilteringService)
        return super().as_view(**initkwargs)

    def __init__(
        self,
        *,
        cache_service=None,
        cache_service_factory=None,
        severity_service=None,
        severity_service_factory=None,
        cache_timeout=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        cache_factory = cache_service_factory or CacheService
        if cache_factory is ORIGINAL_CACHE_SERVICE_CLASS and CacheService is not ORIGINAL_CACHE_SERVICE_CLASS:
            cache_factory = CacheService
        severity_factory = severity_service_factory or SeverityFilteringService
        if severity_factory is ORIGINAL_SEVERITY_SERVICE_CLASS and SeverityFilteringService is not ORIGINAL_SEVERITY_SERVICE_CLASS:
            severity_factory = SeverityFilteringService

        self.cache_service_factory = cache_factory
        self.severity_service_factory = severity_factory
        self.cache_service = cache_service
        self._severity_service = severity_service
        self.cache_timeout = CACHE_TIMEOUT if cache_timeout is None else cache_timeout
        self._current_cache_key = None

    def _get_cache_service(self):
        if self.cache_service is None:
            factory = self.cache_service_factory
            self.cache_service = factory() if callable(factory) else factory
        return self.cache_service

    def _get_severity_service(self):
        if self._severity_service is None:
            factory = self.severity_service_factory
            self._severity_service = factory() if callable(factory) else factory
        return self._severity_service

    def post(self, request):
        """Handle POST requests with JSON payload for filtering"""
        try:
            filter_params = self._extract_filter_parameters(request.data)
            self._current_cache_key = None
            cache_service = self._get_cache_service()
            cached_results = self._generate_cache_key(filter_params)
            cache_key = self._current_cache_key

            if cached_results is not None:  # pragma: no branch
                return Response(cached_results, status=status.HTTP_200_OK)

            if cache_key is None:  # pragma: no branch
                raise ValueError(self.CACHE_KEY_ERROR_SENTINEL)

            severity_filter = self._get_severity_service()
            results = severity_filter.get_filter_stats(**filter_params)
            cache_service.set(cache_key, results, timeout=self.cache_timeout)

            return Response(results, status=status.HTTP_200_OK)

        except CaseFilterValidationError as err:
            return Response(err.as_payload(), status=status.HTTP_400_BAD_REQUEST)
        except ValueError as err:
            if str(err) == self.CACHE_KEY_ERROR_SENTINEL:  # pragma: no branch
                raise
            return Response({"error": str(err)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response(
                {"error": f"Error processing filter request: {str(exc)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _generate_cache_key(self, filter_params):
        cache_service = self._get_cache_service()
        try:
            hashable_items = []
            for key, value in filter_params.items():
                normalized = self._normalize_cache_value(value)
                hashable_items.append((key, normalized))
            cache_key = f"{CACHE_KEY_PREFIX}{hash(frozenset(hashable_items))}"
            self._current_cache_key = cache_key
            return cache_service.get(cache_key)
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

        batch = (
            data.get("batch")
            or data.get("batch_id")
            or data.get("dataset")
            or data.get("dataset_id")
            or data.get("batchId")
            or data.get("datasetId")
        )
        if isinstance(batch, dict):
            batch = batch.get("value") or batch.get("id") or batch.get("batch") or batch.get("data_id")
        if isinstance(batch, (list, tuple, set)):
            batch = next((item for item in batch if item not in (None, "")), None)
        if batch in ([], {}, (), ""):
            batch = None
        
        return {
            'diseases': diseases,
            'provinces': provinces,
            'cities': cities,
            'news_portals': portals,
            'alert_levels': level_of_alertness,
            'date_range': date_range,
            'batch': batch,
        }
    
    def _process_location_data(self, locations):
        """Process location data to extract provinces and cities"""
        if not locations:  # pragma: no branch
            return None, None

        provinces = []
        cities = []

        # Process provinces
        if locations.get('provinces', []):  # pragma: no branch
            for province in locations.get('provinces', []):  # pragma: no branch
                if Location.objects.filter(province=province).exists():  # pragma: no branch
                    provinces.append(province)

        # Process cities
        if locations.get('cities', []):  # pragma: no branch
            for city in locations.get('cities', []):  # pragma: no branch
                if Location.objects.filter(city=city).exists():  # pragma: no branch
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
                lower_msg = error_msg.lower()
                if any(term in lower_msg for term in ("invalid", "duplicate")):
                    return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)
                if "no" in lower_msg and "available" in lower_msg:
                    return build_default_climate_response(ProvinceHumiditySerializer)
                return Response({"error": error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            if not data:
                return build_default_climate_response(ProvinceHumiditySerializer)

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
                lower_msg = error_msg.lower()
                if any(term in lower_msg for term in ("invalid", "duplicate")):
                    return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)
                if "no" in lower_msg and "available" in lower_msg:
                    return build_default_climate_response(ProvincePrecipitationSerializer)
                return Response({"error": error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            if not data:
                return build_default_climate_response(ProvincePrecipitationSerializer)

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
                lower_msg = error_msg.lower()
                if any(term in lower_msg for term in ("invalid", "duplicate")):
                    return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)
                if "no" in lower_msg and "available" in lower_msg:
                    return build_default_climate_response(ProvinceTemperatureSerializer)
                return Response({"error": error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            if not data:
                return build_default_climate_response(ProvinceTemperatureSerializer)

            serializer = ProvinceTemperatureSerializer(data=data, many=True)
            if not serializer.is_valid():
                return Response({"error": CLIMATE_ERROR_INVALID_FORMAT}, status=status.HTTP_400_BAD_REQUEST)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class WeightedSeverityAnalysisView(APIView):
    authentication_classes = [APIKeyRequiredAuthentication, CustomJWTAuthentication]
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
