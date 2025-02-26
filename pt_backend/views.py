from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .repositories import CaseRepository

class AllCaseLocationsView(APIView):
    def get(self, request):
        repository = CaseRepository()
        locations = repository.get_all_case_locations()
        return Response(locations, status=status.HTTP_200_OK)


@require_GET
def hello_world(request):
    return HttpResponse("Hello, World!")

