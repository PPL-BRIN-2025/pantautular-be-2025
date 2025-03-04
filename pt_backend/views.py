from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import CaseService
from .serializers import CaseLocationSerializer

class AllCaseLocationsView(APIView):
    pass



