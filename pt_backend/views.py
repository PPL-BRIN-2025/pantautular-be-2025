from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CaseLocationSerializer
from .services import CaseService
from .authentication import APIKeyAuthentication


class AllCaseLocationsView(APIView):
    authentication_classes = [APIKeyAuthentication]  
    permission_classes = []  

    serializer_class = CaseLocationSerializer
    service = CaseService()
    def get(self, request):
        try:
            cases = self.service.get_all_case_locations()
            if cases is None:
                return Response({"error": "No case locations found"}, status=status.HTTP_404_NOT_FOUND)
            serialized_data = self.serializer_class(cases, many=True).data
            return Response(serialized_data, status=status.HTTP_200_OK)
        except Exception as e: 
            return Response({f"An unexpected error occurred. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



