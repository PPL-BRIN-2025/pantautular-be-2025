from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .repositories import CaseRepository
from django.core.exceptions import ObjectDoesNotExist

class AllCaseLocationsView(APIView):
    def get(self, request):
        repository = CaseRepository()
        try:
            locations = repository.get_all_case_locations()
            return Response(locations, status=status.HTTP_200_OK)
        except ObjectDoesNotExist:
            return Response({"error": "No case locations found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

