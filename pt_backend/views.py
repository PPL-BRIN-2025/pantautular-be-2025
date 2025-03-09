from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CaseLocationSerializer
from .services import CacheService, CaseService
from .filter.service import CaseFilterService
from .repositories import CaseRepository
from .authentication import APIKeyAuthentication


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
            print(e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




