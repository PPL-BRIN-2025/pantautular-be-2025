from rest_framework.test import APIClient
from rest_framework import status
from pt_backend.tests.test_repository import BaseTestCase
from rest_framework.test import APIClient
from rest_framework import status


class FiltersViewTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

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