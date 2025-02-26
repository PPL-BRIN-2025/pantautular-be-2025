from rest_framework.test import APITestCase
from rest_framework import status

class HelloWorldAPITest(APITestCase):
    def test_hello_world_api(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"message": "Hello, World!"})
