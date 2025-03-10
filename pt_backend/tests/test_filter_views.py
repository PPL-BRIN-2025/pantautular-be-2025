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
        self.assertEqual(response.json(), {
            "diseases": ["COVID-19", "Ebola"],
            "locations": ["Jakarta", "Bandung"],
            "news": ["kompas.com", "detik.com"]
        })