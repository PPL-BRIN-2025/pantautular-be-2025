from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


from pt_backend.models import Location
from .serializers import CaseLocationSerializer, DiseaseSeverityStatsSerializer, LocationSeverityStatsSerializer, ProvinceClimateValueSerializer, ProvinceHumiditySerializer, ProvinceTemperatureSerializer, ProvincePrecipitationSerializer
from .services import CacheService, CaseService, CaseDetailService, DiseaseService, LocationService, CasesFilterService, SeverityFilteringService, ClimateService
from .filter.service import CaseFilterService
from .repositories import CaseRepository, DiseaseRepository, LocationRepository, NewsRepository
from .authentication import APIKeyAuthentication
from django.http import Http404
from .formatters import CaseNewsDetailFormatter, CaseHealthProtocolDetailFormatter, CaseGenderDetailFormatter
from .statistics import StatisticsCoordinator, AverageSeverityByProvince
from .filter.grafana_config import (
    measure_time, count_calls,
    CASE_SEARCHED, API_RESPONSE_TIME, API_ERRORS
)

INTERNAL_SERVER_ERR_MSG = "An unexpected error occurred. Please try again later."

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
                cases = self.filter_service.filter_cases(request.data)

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
        except Exception as e:
            print(f"Error in case filter: {str(e)}")
            API_ERRORS.labels(error_type='case_filter_error').inc()
            return Response(
                {"error": INTERNAL_SERVER_ERR_MSG},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class FiltersView(APIView):
    def get(self, request):
        disease_repository = DiseaseRepository()
        location_repository = LocationRepository()
        news_repository = NewsRepository()
        try:
            diseases = [{"value": d, "label": d} for d in disease_repository.get_all_diseases_name()]
            locations = [{"value": l, "label": l} for l in location_repository.get_all_locations_name()]
            news = [{"value": n, "label": n} for n in news_repository.get_all_news_name()]


            response_data = {
                "data": {
                    "diseases": diseases,
                    "locations": locations,
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
    
    def get(self, request):
        try:
            stats = self.service.get_disease_severity_stats()
            
            if isinstance(stats, dict) and "error" in stats:
                return Response(stats, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            serialized_data = self.serializer_class(stats, many=True).data
            return Response({
                "data": serialized_data
            }, status=status.HTTP_200_OK)
            
        except Exception:
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
    
    def get(self, request):
        try:
            stats = self.service.get_province_severity_stats()
            
            if isinstance(stats, dict) and "error" in stats:
                return Response(stats, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            serialized_data = self.serializer_class(stats, many=True).data
            return Response({
                "data": serialized_data
            }, status=status.HTTP_200_OK)
            
        except Exception:
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
    
    def get(self, request):
        try:
            stats = self.service.get_city_severity_stats()
            
            if isinstance(stats, dict) and "error" in stats:
                return Response(stats, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            serialized_data = self.serializer_class(stats, many=True).data
            return Response({
                "data": serialized_data
            }, status=status.HTTP_200_OK)
            
        except Exception:
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
            # Process the request data to match expected filter format
            filter_params = {}
            
            # Handle diseases
            if 'diseases' in request.data and request.data['diseases']:
                filter_params['disease'] = request.data['diseases']
            
            # Handle locations
            if 'locations' in request.data and request.data['locations']:
                filter_params['cities'] = request.data['locations']
            
            # Handle portals
            if 'portals' in request.data and request.data['portals']:
                filter_params['portals'] = request.data['portals']
            
            # Handle alertness level
            if 'level_of_alertness' in request.data and request.data['level_of_alertness'] is not None:
                alertness = int(request.data['level_of_alertness'])
                if alertness > 0:
                    # Option 1: Use the level to filter diseases directly
                    filter_params['disease_alertness'] = alertness
            
            # Handle date range
            start_date = request.data.get('start_date')
            end_date = request.data.get('end_date')
            
            if start_date or end_date:
                # Create a date range even if one value is None
                filter_params['date_range'] = {
                    'start': start_date,
                    'end': end_date
                }
            
            # Generate comprehensive report with processed filters
            statistics = self.statistics_coordinator.generate_comprehensive_report(**filter_params)
            
            return Response(statistics, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(e)
            return Response(
                {"error": "An error occurred while fetching statistics"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
class SeverityFilteringStatsView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    def post(self, request):
        """Handle POST requests with JSON payload for filtering"""
        try:
            # Extract and process filter parameters
            filter_params = self._extract_filter_parameters(request.data)
            
            # Initialize service and get results
            severity_filter = SeverityFilteringService()
            results = severity_filter.get_filter_stats(**filter_params)
            
            return Response(results, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {"error": f"Error processing filter request: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _extract_filter_parameters(self, data):
        """Extract and process filter parameters from request data"""
        # Extract basic filters
        diseases = data.get('diseases', []) or None
        locations = data.get('locations', [])
        portals = data.get('portals', []) or None
        
        # Process location data
        provinces, cities = self._process_location_data(locations)
        
        # Process alertness level
        level_of_alertness = data.get('level_of_alertness') or None
        if level_of_alertness:
            level_of_alertness = int(level_of_alertness)
        
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        date_range = (start_date, end_date) if start_date or end_date else None
        
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
        
        for location in locations:
            # Check if location is a province
            if Location.objects.filter(province=location).exists():
                provinces.append(location)
                continue
            
            # Check if location is a city
            if Location.objects.filter(city=location).exists():
                cities.append(location)
                
                # Add the associated province(s) for each city
                city_provinces = Location.objects.filter(
                    city=location
                ).values_list('province', flat=True).distinct()
                provinces.extend(city_provinces)
        
        # Clean up results
        provinces = list(set(provinces)) if provinces else None
        cities = cities if cities else None
        
        return provinces, cities

class ProvinceHumidityView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    serializer_class = ProvinceHumiditySerializer
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        cache_service = CacheService()
        self.service = ClimateService(cache_service=cache_service)
    
    def get(self, request):
        try:
            humidity_data = self.service.get_province_humidity()
            
            if isinstance(humidity_data, dict) and "error" in humidity_data:
                return Response(humidity_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            serialized_data = self.serializer_class(humidity_data, many=True).data
            return Response(serialized_data, status=status.HTTP_200_OK)
            
        except Exception:
            return Response(
                {"error": INTERNAL_SERVER_ERR_MSG},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ProvincePrecipitationView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    serializer_class = ProvincePrecipitationSerializer
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        cache_service = CacheService()
        self.service = ClimateService(cache_service=cache_service)
    
    def get(self, request):
        try:
            precipitation_data = self.service.get_province_precipitation()
            
            if isinstance(precipitation_data, dict) and "error" in precipitation_data:
                return Response(precipitation_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            serialized_data = self.serializer_class(precipitation_data, many=True).data
            return Response(serialized_data, status=status.HTTP_200_OK)
            
        except Exception:
            return Response(
                {"error": INTERNAL_SERVER_ERR_MSG},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ProvinceTemperatureView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    serializer_class = ProvinceTemperatureSerializer
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        cache_service = CacheService()
        self.service = ClimateService(cache_service=cache_service)
    
    def get(self, request):
        try:
            temperature_data = self.service.get_province_temperature()
            if isinstance(temperature_data, dict) and "error" in temperature_data:
                return Response(temperature_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            serialized_data = self.serializer_class(temperature_data, many=True).data
            return Response({
                "data": serialized_data
            }, status=status.HTTP_200_OK)
            
        except Exception:
            return Response(
                {"error": INTERNAL_SERVER_ERR_MSG},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class WeightedSeverityAnalysisView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
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