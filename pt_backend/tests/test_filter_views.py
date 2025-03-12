from rest_framework.test import APIClient
from rest_framework import status
from pt_backend.tests.test_repository import BaseTestCase


class FiltersViewTest(BaseTestCase):
    def _assert_response_data(self, response_data, expected_data):
        for key in expected_data:
            for item in response_data[key]:
                self.assertIn(item, expected_data[key])
            self.assertEqual(len(response_data[key]), len(expected_data[key]))

    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def test_get_filters(self):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_data = {
            "diseases": ["COVID-19", "Ebola"],
            "locations": ["Jakarta", "Bandung"],
            "news": ["kompas.com", "detik.com"]
        }
        self._assert_response_data(response.json(), expected_data)

