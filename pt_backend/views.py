from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .repositories import CaseRepository
from .serializers import CaseLocationSerializer

class AllCaseLocationsView(APIView):
    def get(self, request):
        repository = CaseRepository()
        try:
            serializer = CaseLocationSerializer
            locations = repository.get_all_case_locations()

            if locations is None:
                return Response({"error": "No case locations found"}, status=status.HTTP_404_NOT_FOUND)

            serialized_data = serializer.serialize(locations=locations)
            return Response(serialized_data, status=status.HTTP_200_OK)

        except Exception as e: 
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


