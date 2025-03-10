from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from pt_backend.models import Case, Disease, Location, News
from pt_backend.repositories import DiseaseRepository, LocationRepository, NewsRepository
from django.core.exceptions import ObjectDoesNotExist
import uuid
from unittest.mock import patch
from .test_repository import BaseTestCase

class FilterAPITest(BaseTestCase):
    def test_get_filters(self):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {
            "diseases": ["COVID-19", "Ebola"],
            "locations": ["Jakarta", "Bandung"],
            "news": ["kompas.com", "detik.com"]
        })
    
    def test_get_filters_empty(self):
        Disease.objects.all().delete()
        Location.objects.all().delete()
        News.objects.all().delete()

        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {
            "diseases": [],
            "locations": [],
            "news": []
        })

    @patch('pt_backend.repositories.DiseaseRepository.get_all_diseases_name', side_effect=ObjectDoesNotExist)
    def test_get_filters_exception(self, mock_get_all_diseases_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"error": "No diseases found"})
    
    @patch('pt_backend.repositories.DiseaseRepository.get_all_diseases_name', side_effect=Exception("Database error"))
    def test_get_filters_exception(self, mock_get_all_diseases_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.json())

    @patch('pt_backend.repositories.LocationRepository.get_all_locations_name', side_effect=ObjectDoesNotExist)
    def test_get_filters_exception(self, mock_get_all_locations_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"error": "No locations found"})
    
    @patch('pt_backend.repositories.LocationRepository.get_all_locations_name', side_effect=Exception("Database error"))
    def test_get_filters_exception(self, mock_get_all_locations_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.json())

    @patch('pt_backend.repositories.NewsRepository.get_all_news_name', side_effect=ObjectDoesNotExist)
    def test_get_filters_exception(self, mock_get_all_news_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"error": "No news found"})

    @patch('pt_backend.repositories.NewsRepository.get_all_news_name', side_effect=Exception("Database error"))
    def test_get_filters_exception(self, mock_get_all_news_name):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.json())