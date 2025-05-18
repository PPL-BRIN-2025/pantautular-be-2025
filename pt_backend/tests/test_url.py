from rest_framework.test import APIClient
from rest_framework import status
from pt_backend.tests.test_repository import BaseTestCase

class FilterAPITest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def test_filters_url_exists(self):
        response = self.client.get('/api/filters/')
        self.assertNotEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filters_url_allows_get(self):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filters_url_denies_post(self):
        response = self.client.post('/api/filters/', {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

class HealthCheckURLTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def test_health_check_url_exists(self):
        response = self.client.get('/health/')
        self.assertNotEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_health_check_url_allows_get(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health_check_url_denies_post(self):
        response = self.client.post('/health/', {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
