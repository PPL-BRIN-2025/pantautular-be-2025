import os
from django.test import TestCase
from unittest.mock import Mock
from datetime import datetime
from pt_backend.formatters import (
    CaseNewsDetailFormatter, 
    CaseHealthProtocolDetailFormatter,
    CaseGenderDetailFormatter
)



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
