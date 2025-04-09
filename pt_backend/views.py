from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CaseLocationSerializer, DiseaseSeverityStatsSerializer, LocationSeverityStatsSerializer, PrevalenceSerializer
from .services import CacheService, CaseService, CaseDetailService, DiseaseService, LocationService, CasesFilterService
from .filter.service import CaseFilterService
from .repositories import CaseRepository, DiseaseRepository, LocationRepository, NewsRepository
from .authentication import APIKeyAuthentication
from django.http import Http404
from .formatters import CaseNewsDetailFormatter, CaseHealthProtocolDetailFormatter, CaseGenderDetailFormatter
import logging
from .statistics import StatisticsCoordinator
logger = logging.getLogger(__name__)

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

    def post(self, request):
        try:
            if not request.data or all(not v for v in request.data.values()):
                cases = self.service.get_all_case_locations()

            else: 
                cases = self.filter_service.filter_cases(request.data)

            if not cases:
                return Response(
                    {"error": INTERNAL_SERVER_ERR_MSG},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                self.serializer_class(cases, many=True).data,
                status=status.HTTP_200_OK
            )
        except Exception as e:
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
        
class SeverityDatesView(APIView):
    def get(self, request):
        news_repository = NewsRepository()
        try:
            severity_dates = news_repository.get_all_severities_dates()
            for item in severity_dates:
                if 'date_published' in item:
                    item['date_published'] = item['date_published'].date()
            if len(severity_dates) == 0:
                return Response({"error": "No severity dates found"}, status=status.HTTP_404_NOT_FOUND)
            return Response({"data": severity_dates}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            return Response(
                {"error": f"An error occurred while fetching statistics: {str(e)}"},
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
                filter_params['provinces'] = request.data['locations']
            
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
            return Response(
                {"error": f"An error occurred while fetching statistics: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
