from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CaseLocationSerializer, PrevalenceSerializer
from .services import CacheService, CaseService
from .filter.service import CaseFilterService
from .repositories import CaseRepository, DiseaseRepository, LocationRepository, NewsRepository
from .authentication import APIKeyAuthentication
from .statistics import PrevalenceStatistics

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
            if not cases:
                return Response({"error": "No case locations found"}, status=status.HTTP_404_NOT_FOUND)
            serialized_data = self.serializer_class(cases, many=True).data
            return Response(serialized_data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({"error": "An unexpected error occurred. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            if not request.data or all(not v for v in request.data.values()):
                cases = self.service.get_all_case_locations()

            else: 
                cases = self.filter_service.filter_cases(request.data)

            if not cases:
                return Response(
                    {"error": "No case locations found matching the filters"},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                self.serializer_class(cases, many=True).data,
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
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

class DiseaseCaseInfoView(APIView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.repository = CaseRepository()
        # Initialize other needed repositories here
        self.prevalence_statistics = PrevalenceStatistics(self.repository)
        # Initialize other statistics here
    
    def check_statistics_errors(self, stats_data):
        for component_name, data in stats_data.items():
            if isinstance(data, dict) and "error" in data:
                error_message = data["error"]                
                if "not available" in error_message:
                    status_code = status.HTTP_404_NOT_FOUND
                else:
                    status_code = status.HTTP_400_BAD_REQUEST
                    
                return True, Response(
                    {"error": error_message, "component": component_name}, 
                    status=status_code
                )        
        return False, None
    
    def get(self, request):
        try:
            # Get all query parameters, assuming filters are passed as query parameters
            start_date = request.query_params.get('start_date')
            # Add other query parameters here
            
            # Collect statistics from all components
            stats_data = {
                "prevalence_statistics": self.prevalence_statistics.get_prevalence_statistics(start_date),
                # Add other statistics components here
            }
            
            # Check for errors in any of the statistics components
            has_error, error_response = self.check_statistics_errors(stats_data)
            if has_error:
                return error_response
            
            return Response(stats_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
