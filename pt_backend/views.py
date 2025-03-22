from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CaseLocationSerializer, GenderDistributionSerializer
from .services import CacheService, CaseService
from .filter.service import CaseFilterService
from .repositories import CaseRepository, DiseaseRepository, LocationRepository, NewsRepository
from .authentication import APIKeyAuthentication
import logging

logger = logging.getLogger(__name__)
INTERNAL_ERROR_MESSAGE = "An unexpected error occurred. Please try again later."

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
            return Response({"error": INTERNAL_ERROR_MESSAGE}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            if not request.data or all(not v for v in request.data.values()):
                cases = self.service.get_all_case_locations()

            else: 
                cases = self.filter_service.filter_cases(request.data)

            if not cases:
                return Response(
                    {"error": INTERNAL_ERROR_MESSAGE},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                self.serializer_class(cases, many=True).data,
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": INTERNAL_ERROR_MESSAGE},
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

class CaseGenderView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        repository = CaseRepository()
        cache_service = CacheService()
        self.service = CaseService(repository, cache_service)
    
    def get(self, request):
        try:
            gender_distribution = self.service.get_gender_dist()
            serialized_data = GenderDistributionSerializer(gender_distribution)
            return Response(serialized_data.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in get method: {e}", exc_info=True)
            return Response({"error": INTERNAL_ERROR_MESSAGE}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)