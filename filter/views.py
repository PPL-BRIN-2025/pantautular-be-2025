from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pt_backend.repositories import DiseaseRepository, LocationRepository, NewsRepository

class FiltersView(APIView):
    def get(self, request):
        disease_repository = DiseaseRepository()
        location_repository = LocationRepository()
        news_repository = NewsRepository()
        try:
            diseases = disease_repository.get_all_diseases_name()
            locations = location_repository.get_all_locations_name()
            news = news_repository.get_all_news_name()
            return Response(
                {
                    "diseases": diseases,
                    "locations": locations,
                    "news": news
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)