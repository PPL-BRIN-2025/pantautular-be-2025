from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CaseLocationSerializer
from .services import CacheService, CaseService, CaseDetailService
from .filter.service import CaseFilterService
from .repositories import CaseRepository, DiseaseRepository, LocationRepository, NewsRepository
from .authentication import APIKeyAuthentication
from django.http import Http404
from .formatters import CaseNewsDetailFormatter, CaseHealthProtocolDetailFormatter, CaseGenderDetailFormatter


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