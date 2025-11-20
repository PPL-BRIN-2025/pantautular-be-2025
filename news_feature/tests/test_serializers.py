from datetime import datetime, timezone as dt_timezone
import uuid

from django.test import TestCase, override_settings

from pt_backend.models import Case, Disease, Location, News

from news_feature.serializers import NewsArticleSerializer


class NewsArticleSerializerTests(TestCase):
    def setUp(self):
        self.case = self._create_case()
        self.article = self._create_news(type="Kurasi", img_url="https://img/serializer.jpg")

    def _create_case(self):
        disease = Disease.objects.create(name="Malaria", level_of_alertness=1)
        location = Location.objects.create(
            city="Jakarta",
            province="DKI Jakarta",
            latitude=0,
            longitude=0,
        )
        return Case.objects.create(
            gender="male",
            age=22,
            city="Jakarta",
            status=Case.STATUS_CHOICES[0][0],
            severity=Case.SEVERITY_CHOICES[0][0],
            disease=disease,
            location=location,
        )

    def _create_news(self, **overrides):
        base = {
            "portal": "Kompas",
            "title": "Serializer",
            "type": "Nasional",
            "content": "Serializer summary",
            "url": f"https://example.com/{uuid.uuid4()}",
            "author": "Reporter",
            "date_published": datetime(2025, 1, 1, tzinfo=dt_timezone.utc),
            "img_url": "",
            "case": self.case,
        }
        base.update(overrides)
        return News.objects.create(**base)

    def test_curated_fields_map_from_type(self):
        data = NewsArticleSerializer(self.article).data
        self.assertEqual(data["curated_tags"], ["Kurasi"])
        self.assertTrue(data["is_curated"])
        self.assertEqual(data["source_name"], "Kompas")

    @override_settings(NEWS_DEFAULT_IMAGE_URL="https://cdn.example.com/default.jpg")
    def test_thumbnail_falls_back_to_default_image(self):
        article = self._create_news(type="Health", img_url="")
        data = NewsArticleSerializer(article).data
        self.assertEqual(data["thumbnail_url"], "https://cdn.example.com/default.jpg")
        self.assertEqual(data["curated_tags"], ["Health"])
