from rest_framework import status

from pt_backend.models import Disease, Location, News
from unittest.mock import patch
from .test_repository import BaseTestCase

class FilterAPITest(BaseTestCase):
    def test_get_filters(self):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        expected_diseases = ["COVID-19", "Ebola"]
        expected_locations = ["Jakarta", "Bandung"]
        expected_news = ["kompas.com", "detik.com"]

        for disease in response_data["diseases"]:
            self.assertIn(disease, expected_diseases)
        self.assertEqual(len(response_data["diseases"]), len(expected_diseases))
        
        for location in response_data["locations"]:
            self.assertIn(location, expected_locations)
        self.assertEqual(len(response_data["locations"]), len(expected_locations))
        
        for news in response_data["news"]:
            self.assertIn(news, expected_news)
        self.assertEqual(len(response_data["news"]), len(expected_news))
    
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

    def _test_get_filters_exception(self, patch_target, side_effect, expected_status, expected_error):
        with patch(patch_target, side_effect=side_effect):
            response = self.client.get('/api/filters/')
            self.assertEqual(response.status_code, expected_status)
            self.assertEqual(response.json(), {"error": expected_error})

    def test_get_filters_disease_db_error(self):
        self._test_get_filters_exception(
            'pt_backend.repositories.DiseaseRepository.get_all_diseases_name',
            Exception("Database error"),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Database error"
        )

    def test_get_filters_location_db_error(self):
        self._test_get_filters_exception(
            'pt_backend.repositories.LocationRepository.get_all_locations_name',
            Exception("Database error"),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Database error"
        )

    def test_get_filters_news_db_error(self):
        self._test_get_filters_exception(
            'pt_backend.repositories.NewsRepository.get_all_news_name',
            Exception("Database error"),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Database error"
        )