import os
from django.test import TestCase
from unittest.mock import Mock, patch, call
from datetime import datetime
from pt_backend.models import Case, Disease, Location, News
from pt_backend.formatters import (
   CaseNewsDetailFormatter,
   CaseHealthProtocolDetailFormatter,
   CaseGenderDetailFormatter
)
from pt_backend.services import CaseDetailService
from pt_backend.repositories import CaseRepository
import uuid
from rest_framework.test import APITestCase, APIClient
from django.urls import reverse
from rest_framework import status
from django.utils import timezone


class BaseCaseDetailTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        os.environ['SECRET_API_KEY'] = 'test-api-key'
        self.client.credentials(HTTP_X_API_KEY='test-api-key')
        
        self._create_test_data()

    def tearDown(self):
        os.environ.pop('SECRET_API_KEY', None)

    def _create_test_data(self):
        self.disease = Disease.objects.create(
            name="Test Disease",
            level_of_alertness=1
        )
        
        self.location = Location.objects.create(
            latitude=0.0,
            longitude=0.0,
            city="Test City",
            province="Test Province"
        )
        
        self.case = Case.objects.create(
            id=uuid.uuid4(),
            gender="Pria",
            age=25,
            city="Test City",
            status="terjangkit",
            severity="hospitalisasi",
            disease=self.disease,
            location=self.location
        )
        
        self.news = News.objects.create(
            title="Test News",
            content="Test Content",
            url="https://test.com",
            portal="Test Portal",
            type="article",
            author="Test Author",
            date_published=timezone.now(),
            case=self.case
        )

    def _assert_case_detail_response_http(self, response):
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['id']), str(self.case.id))
        self.assertEqual(response.data['gender'], self.case.gender)
        self.assertEqual(response.data['age'], self.case.age)
        self.assertEqual(response.data['location'], self.location.province)
        self.assertEqual(len(response.data['news']), 1)
        self.assertEqual(response.data['news'][0]['title'], self.news.title)

    def _assert_case_detail_response_dict(self, result):
        self.assertEqual(result["id"], self.case_id)
        self.assertEqual(result["location"], "Jakarta")
        self.assertEqual(result["gender"], "Pria")
        self.assertEqual(result["age"], 25)
        self.assertEqual(result["level_of_alertness"], 3)
        self.assertEqual(
            result["related_search"],
            "https://www.google.com/search?q=Apa+itu+COVID-19"
        )
        self.assertEqual(len(result["news"]), 1)
        self.assertEqual(len(result["health_protocols"]), 1)
        self.assertEqual(result["news"][0]["title"], "Test News")
        self.assertEqual(result["health_protocols"][0]["title"], "Test Protocol")


class CaseDetailFormatterTest(BaseCaseDetailTest):
    def setUp(self):
        super().setUp()
        self.formatters = {
            'news': CaseNewsDetailFormatter(),
            'protocol': CaseHealthProtocolDetailFormatter(),
            'gender': CaseGenderDetailFormatter()
        }

    def test_news_formatter(self):
        result = self.formatters['news'].format(self.news)
        expected = {
            "img_url": "",
            "url": "https://test.com",
            "title": "Test News",
            "domain": "test.com",
            "date": timezone.now().strftime("%d %b %Y"),
            "content": "Test Content"
        }
        self.assertEqual(result, expected)

    def test_protocol_formatter(self):
        protocol = Mock(title="Test Protocol", url="https://example.com/protocol/1")
        result = self.formatters['protocol'].format(protocol)
        self.assertEqual(result, {"title": "Test Protocol", "url": "https://example.com/protocol/1"})

    def test_gender_formatter(self):
        test_cases = [
            ("Male", "Pria"),
            ("Female", "Perempuan"),
            ("Other", "Other")
        ]
        for input_gender, expected in test_cases:
            with self.subTest(gender=input_gender):
                self.assertEqual(self.formatters['gender'].format(input_gender), expected)

    def test_extract_domain(self):
        test_cases = [
            (None, ""),
            ("invalid-url", ""),
            ("https://test.com", "test.com")
        ]
        for url, expected in test_cases:
            with self.subTest(url=url):
                result = CaseNewsDetailFormatter._extract_domain(url)
                self.assertEqual(result, expected)

class CaseDetailServiceTest(BaseCaseDetailTest):
    def setUp(self):
        super().setUp()
        self.repository = Mock()
        self.cache_service = Mock()
        self.service = CaseDetailService(
            repository=self.repository,
            cache_service=self.cache_service,
            news_formatter=CaseNewsDetailFormatter(),
            protocol_formatter=CaseHealthProtocolDetailFormatter(),
            gender_formatter=CaseGenderDetailFormatter()
        )
        self.case_id = self.case.id

    def _create_mock_case(self):
        case = Mock()
        case.id = self.case_id
        case.gender = "Male"
        case.age = 25
        case.location = Mock(province="Jakarta")
        
        # Create disease mock with proper name handling
        disease = Mock()
        disease.name = "COVID-19"
        disease.level_of_alertness = 3
        case.disease = disease
        
        return case

    def test_get_case_detail_from_cache(self):
        cached_data = {"id": self.case_id, "cached": True}
        self.cache_service.get.return_value = cached_data
        result = self.service.get_case_detail(self.case_id)
        self.assertEqual(result, cached_data)
        self.repository.get_case_detail_by_id.assert_not_called()

    def test_get_case_detail_not_found(self):
        self.cache_service.get.return_value = None
        self.repository.get_case_detail_by_id.return_value = None
        result = self.service.get_case_detail(self.case_id)
        self.assertIsNone(result)

    def test_get_case_detail_success(self):
        mock_case = self._create_mock_case()
        mock_case.news.all.return_value = [self.news]
        mock_case.disease.protocols.all.return_value = [Mock(health_protocol=Mock(title="Test Protocol", url="https://example.com/protocol/1"))]
        
        self.cache_service.get.return_value = None
        self.repository.get_case_detail_by_id.return_value = mock_case
        
        result = self.service.get_case_detail(self.case_id)
        self._assert_case_detail_response(result)
        self.cache_service.set.assert_called_once()

    def test_format_news_with_exception(self):
        news = Mock(date_published="invalid date")
        self.service._format_news([news])

    def test_format_health_protocols_with_exception(self):
        disease = Mock()
        disease.protocols.all.side_effect = Exception("Database error")
        result = self.service._format_health_protocols(disease)
        self.assertEqual(result, [])

    def test_generate_related_search_with_none(self):
        result = self.service._generate_related_search(None)
        self.assertIsNone(result)

    def test_get_case_detail_with_exception(self):
        self.cache_service.get.return_value = None
        self.repository.get_case_detail_by_id.side_effect = Exception("Database error")
        with self.assertRaises(Exception):
            self.service.get_case_detail(self.case_id)

    def test_format_news_with_none(self):
        result = self.service._format_news(None)
        self.assertEqual(result, [])

    def test_format_health_protocols_with_none(self):
        result = self.service._format_health_protocols(None)
        self.assertEqual(result, [])

    def test_get_case_detail_raises_exception(self):
        self.cache_service.get.return_value = None
        mock_case = self._create_mock_case()
        mock_case.news.all.side_effect = Exception("Database error")
        self.repository.get_case_detail_by_id.return_value = mock_case
        with self.assertRaises(Exception):
            self.service.get_case_detail(self.case_id)

class CaseRepositoryTest(BaseCaseDetailTest):
    def test_get_case_detail_by_id_exception(self):
        mock_case = Mock()
        mock_case.DoesNotExist = type('DoesNotExist', (Exception,), {})
        mock_case.objects.select_related.side_effect = Exception("Database error")
        
        with patch('pt_backend.repositories.Case', mock_case):
            repository = CaseRepository()
            result = repository.get_case_detail_by_id(uuid.uuid4())
            self.assertIsNone(result)

    def test_get_case_detail_by_id_not_found(self):
        mock_case = Mock()
        mock_case.DoesNotExist = type('DoesNotExist', (Exception,), {})
        mock_case.objects.select_related.side_effect = mock_case.DoesNotExist("Case not found")
        
        with patch('pt_backend.repositories.Case', mock_case):
            repository = CaseRepository()
            result = repository.get_case_detail_by_id(uuid.uuid4())
            self.assertIsNone(result)

class CaseDetailViewTest(BaseCaseDetailTest):
    def test_get_case_detail_not_found(self):
        non_existent_id = uuid.uuid4()
        url = reverse('case-detail', args=[non_existent_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['detail'], 'Not found.')

    def test_get_case_detail_success(self):
        url = reverse('case-detail', args=[self.case.id])
        response = self.client.get(url)
        self._assert_case_detail_response(response)

    def test_get_case_detail_unauthorized(self):
        self.client.credentials()
        url = reverse('case-detail', args=[self.case.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
