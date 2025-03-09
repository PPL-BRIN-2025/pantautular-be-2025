from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from django.test import TestCase
from pt_backend.models import Case, Disease, Location, News
from pt_backend.repositories import DiseaseRepository, LocationRepository, NewsRepository
import uuid

class FiltersViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.diseaseRepository = DiseaseRepository()
        self.locationRepository = LocationRepository()
        self.newsRepository = NewsRepository()

        self.disease1 = Disease.objects.create(name="COVID-19", level_of_alertness=5)
        self.disease2 = Disease.objects.create(name="Ebola", level_of_alertness=4)

        self.location1 = Location.objects.create(id=uuid.uuid4(), latitude=-6.2088, longitude=106.8456, name="Jakarta")
        self.location2 = Location.objects.create(id=uuid.uuid4(), latitude=-6.9175, longitude=107.6191, name="Bandung")

        self.case1 = Case.objects.create(
            id=uuid.uuid4(),
            gender="Pria",
            age=30,
            city="Jakarta",
            status="kematian",
            disease=self.disease1,
            location=self.location1
        )
        self.case2 = Case.objects.create(
            id=uuid.uuid4(),
            gender="Wanita",
            age=25,
            city="Bandung",
            status="terjangkit",
            disease=self.disease2,
            location=self.location2
        )

        self.news1 = News.objects.create(
            id=uuid.uuid4(),
            portal="kompas.com",
            type="health",
            title="COVID-19 Detected in Jakarta",
            content="COVID-19 case detected in Jakarta...",
            url="https://www.kompas.com/covid-jakarta",
            author="Dr. Joko",
            case=self.case1
        )
        self.news2 = News.objects.create(
            id=uuid.uuid4(),
            portal="detik.com",
            type="health",
            title="SARS Detected in Medan",
            content="SARS case detected in Medan...",
            url="https://www.detik.com/sars-medan",
            author="Dr. Sari",
            case=self.case2
        )

    def test_get_filters(self):
        response = self.client.get('/api/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {
            "diseases": ["COVID-19", "Ebola"],
            "locations": ["Jakarta", "Bandung"],
            "news": ["kompas.com", "detik.com"]
        })
