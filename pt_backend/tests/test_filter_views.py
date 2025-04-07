from rest_framework.test import APIClient
from rest_framework import status
from pt_backend.tests.test_repository import BaseTestCase
from pt_backend.models import Disease, Location, News, Case


class FiltersViewTest(BaseTestCase):
    def _assert_response_data(self, response_data, expected_data):
        response_data = response_data['data']
        for key in expected_data:
            actual_values = [item['value'] for item in response_data[key]]
            for expected_item in expected_data[key]:
                self.assertIn(expected_item, actual_values)

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        
        # Create test diseases
        self.disease1 = Disease.objects.create(
            name="COVID-19",
            level_of_alertness=1
        )
        self.disease2 = Disease.objects.create(
            name="Ebola",
            level_of_alertness=1
        )
        
        # Create test locations
        self.location1 = Location.objects.create(
            city="Jakarta",
            province="DKI Jakarta",
            latitude="-6.200000",
            longitude="106.816666"
        )
        self.location2 = Location.objects.create(
            city="Bandung",
            province="Jawa Barat",
            latitude="-6.914744",
            longitude="107.609810"
        )
        
        # Create a case (needed for news)
        self.case = Case.objects.create(
            gender="Male",
            age=30,
            city="Jakarta",
            status="minimal",
            severity="insiden",
            disease=self.disease1,
            location=self.location1
        )
        
        # Create test news
        self.news1 = News.objects.create(
            portal="kompas.com",
            title="Test News 1",
            type="article",
            content="Test content",
            url="https://kompas.com/test1",
            author="Author 1",
            case=self.case
        )
        self.news2 = News.objects.create(
            portal="detik.com",
            title="Test News 2",
            type="article",
            content="Test content",
            url="https://detik.com/test2",
            author="Author 2",
            case=self.case
        )

    def test_get_filters(self):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        expected_data = {
            "data": {
                "diseases": [
                    {"value": "COVID-19", "label": "COVID-19"},
                    {"value": "Ebola", "label": "Ebola"}
                ],
                "locations": [
                    {"value": "Jakarta", "label": "Jakarta"},
                    {"value": "Bandung", "label": "Bandung"}
                ],
                "news": [
                    {"value": "kompas.com", "label": "kompas.com"},
                    {"value": "detik.com", "label": "detik.com"}
                ]
            }
        }
        
        self.assertEqual(response.json(), expected_data)

    def test_get_filters_empty(self):
        # Clear all data
        News.objects.all().delete()
        Case.objects.all().delete()
        Disease.objects.all().delete()
        Location.objects.all().delete()
        
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_empty_data = {
            "data": {
                "diseases": [],
                "locations": [],
                "news": []
            }
        }
        self.assertEqual(response.json(), expected_empty_data)

