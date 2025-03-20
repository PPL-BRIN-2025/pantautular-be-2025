import os
from django.test import TestCase
from unittest.mock import Mock
from datetime import datetime
from pt_backend.formatters import (
    CaseNewsDetailFormatter, 
    CaseHealthProtocolDetailFormatter,
    CaseGenderDetailFormatter
)
import uuid
from pt_backend.services import CaseDetailService



class CaseDetailFormatterTest(TestCase):
    def setUp(self):
        self.news_formatter = CaseNewsDetailFormatter()
        self.protocol_formatter = CaseHealthProtocolDetailFormatter()
        self.gender_formatter = CaseGenderDetailFormatter()

    def test_news_formatter(self):
        news = Mock()
        news.img_url = "http://example.com/image.jpg"
        news.url = "http://example.com/news/1"
        news.date_published = datetime.strptime("2024-03-20T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ")
        news.title = "Test News"

        result = self.news_formatter.format(news)
        
        self.assertEqual(result["img_url"], "http://example.com/image.jpg")
        self.assertEqual(result["url"], "http://example.com/news/1")
        self.assertEqual(result["title"], "Test News")
        self.assertEqual(result["domain"], "example.com")
        self.assertEqual(result["date"], "20 Mar 2024")

    def test_protocol_formatter(self):
        protocol = Mock()
        protocol.title = "Test Protocol"
        protocol.url = "http://example.com/protocol/1"

        result = self.protocol_formatter.format(protocol)

        self.assertEqual(result["title"], "Test Protocol")
        self.assertEqual(result["url"], "http://example.com/protocol/1")

    def test_gender_formatter(self):
        self.assertEqual(self.gender_formatter.format("Male"), "Laki-laki")
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
           img_url="http://example.com/image.jpg",
           url="http://example.com/news/1",
           date_published=datetime.now(),
           title="Test News"
       )
       case.news.all.return_value = [news]


       protocol = Mock()
       protocol.health_protocol = Mock(
           title="Test Protocol",
           url="http://example.com/protocol/1"
       )
       case.disease.protocols.all.return_value = [protocol]


       self.cache_service.get.return_value = None
       self.repository.get_case_detail_by_id.return_value = case
      
       result = self.service.get_case_detail(case.id)


       self.assertEqual(result["id"], case.id)
       self.assertEqual(result["location"], "Jakarta")
       self.assertEqual(result["gender"], "Laki-laki")
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