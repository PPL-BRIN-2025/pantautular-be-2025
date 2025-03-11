from rest_framework import status

from pt_backend.models import Disease, Location, News
from unittest.mock import patch
from .test_repository import BaseTestCase

class FilterAPITest(BaseTestCase):
    def _assert_response_data(self, response_data, expected_data):
        for key in expected_data:
            for item in response_data[key]:
                self.assertIn(item, expected_data[key])
            self.assertEqual(len(response_data[key]), len(expected_data[key]))

    def test_get_filters(self):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_data = {
            "diseases": ["COVID-19", "Ebola"],
            "locations": ["Jakarta", "Bandung"],
            "news": ["kompas.com", "detik.com"]
        }
        self._assert_response_data(response.json(), expected_data)
    
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