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



class CaseDetailFormatterTest(TestCase):
    def setUp(self):
        self.news_formatter = CaseNewsDetailFormatter()
        self.protocol_formatter = CaseHealthProtocolDetailFormatter()
        self.gender_formatter = CaseGenderDetailFormatter()

    def test_news_formatter(self):
        news = Mock()
        news.img_url = "https://example.com/image.jpg"
        news.url = "https://example.com/news/1"
        news.date_published = datetime.strptime("2024-03-20T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ")
        news.title = "Test News"
        news.content = "News content"

        result = self.news_formatter.format(news)
        
        self.assertEqual(result["img_url"], "https://example.com/image.jpg")
        self.assertEqual(result["url"], "https://example.com/news/1")
        self.assertEqual(result["title"], "Test News")
        self.assertEqual(result["domain"], "example.com")
        self.assertEqual(result["date"], "20 Mar 2024")
        self.assertEqual(result["content"], "News content")

    def test_protocol_formatter(self):
        protocol = Mock()
        protocol.title = "Test Protocol"
        protocol.url = "https://example.com/protocol/1"

        result = self.protocol_formatter.format(protocol)

        self.assertEqual(result["title"], "Test Protocol")
        self.assertEqual(result["url"], "https://example.com/protocol/1")

    def test_gender_formatter(self):
        self.assertEqual(self.gender_formatter.format("Male"), "Pria")
        self.assertEqual(self.gender_formatter.format("Female"), "Perempuan")
        self.assertEqual(self.gender_formatter.format("Other"), "Other")

    def test_extract_domain_with_none_url(self):
        result = CaseNewsDetailFormatter._extract_domain(None)
        self.assertEqual(result, "")

    def test_extract_domain_with_invalid_url(self):
        result = CaseNewsDetailFormatter._extract_domain("invalid-url")
        self.assertEqual(result, "")


class CaseDetailServiceTest(TestCase):
   def setUp(self):
       self.repository = Mock()
       self.cache_service = Mock()
       self.news_formatter = CaseNewsDetailFormatter()
       self.protocol_formatter = CaseHealthProtocolDetailFormatter()
       self.gender_formatter = CaseGenderDetailFormatter()
      
       self.service = CaseDetailService(
           repository=self.repository,
           cache_service=self.cache_service,
           news_formatter=self.news_formatter,
           protocol_formatter=self.protocol_formatter,
           gender_formatter=self.gender_formatter
       )


   def test_get_case_detail_from_cache(self):
       case_id = uuid.uuid4()
       cached_data = {"id": case_id, "cached": True}
       self.cache_service.get.return_value = cached_data
      
       result = self.service.get_case_detail(case_id)
      
       self.assertEqual(result, cached_data)
       self.repository.get_case_detail_by_id.assert_not_called()


   def test_get_case_detail_not_found(self):
       self.cache_service.get.return_value = None
       self.repository.get_case_detail_by_id.return_value = None
      
       result = self.service.get_case_detail(uuid.uuid4())
      
       self.assertIsNone(result)


   def test_get_case_detail_success(self):
       case = Mock()
       case.id = uuid.uuid4()
       case.gender = "Male"
       case.age = 25
       case.location = Mock(province="Jakarta")
      
       disease = Mock()
       disease.name = "COVID-19"  
       disease.level_of_alertness = 3
       case.disease = disease
      
       news = Mock(
           img_url="https://example.com/image.jpg",
           url="https://example.com/news/1",
           date_published=timezone.now(),
           title="Test News",
           content = "News content"
       )
       case.news.all.return_value = [news]


       protocol = Mock()
       protocol.health_protocol = Mock(
           title="Test Protocol",
           url="https://example.com/protocol/1"
       )
       case.disease.protocols.all.return_value = [protocol]


       self.cache_service.get.return_value = None
       self.repository.get_case_detail_by_id.return_value = case
      
       result = self.service.get_case_detail(case.id)


       self.assertEqual(result["id"], case.id)
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
      
       self.cache_service.set.assert_called_once()


   def test_format_news_with_exception(self):
       news = Mock()
       news.date_published = "invalid date" 
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
           self.service.get_case_detail(uuid.uuid4())


   def test_format_news_with_none(self):
       result = self.service._format_news(None)
       self.assertEqual(result, [])


   def test_format_health_protocols_with_none(self):
       result = self.service._format_health_protocols(None)
       self.assertEqual(result, [])


   def test_get_case_detail_raises_exception(self):
       self.cache_service.get.return_value = None
       case = Mock()
       case.news.all.side_effect = Exception("Database error")  
       self.repository.get_case_detail_by_id.return_value = case

       with self.assertRaises(Exception):
           self.service.get_case_detail(uuid.uuid4())

class CaseRepositoryTest(TestCase):
   def test_get_case_detail_by_id_exception(self):
       # Create a mock Case model with DoesNotExist exception
       mock_case = Mock()
       mock_case.DoesNotExist = type('DoesNotExist', (Exception,), {})
       mock_case.objects.select_related.side_effect = Exception("Database error")
       
       with patch('pt_backend.repositories.Case', mock_case):
           repository = CaseRepository()
           result = repository.get_case_detail_by_id(uuid.uuid4())
           self.assertIsNone(result)

   def test_get_case_detail_by_id_not_found(self):
       # Create a mock Case model with DoesNotExist exception
       mock_case = Mock()
       mock_case.DoesNotExist = type('DoesNotExist', (Exception,), {})
       mock_case.objects.select_related.side_effect = mock_case.DoesNotExist("Case not found")
       
       with patch('pt_backend.repositories.Case', mock_case):
           repository = CaseRepository()
           non_existent_id = uuid.uuid4()
           result = repository.get_case_detail_by_id(non_existent_id)
           self.assertIsNone(result)


class CaseDetailViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Set up API key authentication
        os.environ['SECRET_API_KEY'] = 'test-api-key'
        self.client.credentials(HTTP_X_API_KEY='test-api-key')
        
        # Create test data
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

    def tearDown(self):
        # Clean up environment variable
        os.environ.pop('SECRET_API_KEY', None)

    def test_get_case_detail_not_found(self):
        """Test getting a non-existent case detail"""
        non_existent_id = uuid.uuid4()
        url = reverse('case-detail', args=[non_existent_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('detail', response.data)
        self.assertEqual(response.data['detail'], 'Not found.')

    def test_get_case_detail_success(self):
        """Test getting an existing case detail"""
        url = reverse('case-detail', args=[self.case.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['id']), str(self.case.id))
        self.assertEqual(response.data['gender'], self.case.gender)
        self.assertEqual(response.data['age'], self.case.age)
        self.assertEqual(response.data['location'], self.location.province)
        self.assertEqual(len(response.data['news']), 1)
        self.assertEqual(response.data['news'][0]['title'], self.news.title)

    def test_get_case_detail_unauthorized(self):
        """Test getting case detail without authentication"""
        # Remove API key credentials
        self.client.credentials()
        
        url = reverse('case-detail', args=[self.case.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
