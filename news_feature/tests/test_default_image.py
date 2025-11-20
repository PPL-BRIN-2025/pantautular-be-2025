from django.test import TestCase, override_settings
from django.utils import timezone

from news_feature.models import NewsArticle
from news_feature.services.default_image import assign_default_thumbnail


class AssignDefaultThumbnailTests(TestCase):
    def _create_article(self, **overrides):
        defaults = {
            "title": "Default title",
            "summary": "Summary",
            "source_url": f"https://example.com/{timezone.now().timestamp()}",
            "source_name": "Example Source",
            "thumbnail_url": overrides.pop("thumbnail_url", None),
            "published_at": timezone.now(),
        }
        defaults.update(overrides)
        return NewsArticle.objects.create(**defaults)

    @override_settings(NEWS_DEFAULT_IMAGE_URL="https://cdn.example.com/default.jpg")
    def test_assigns_default_thumbnail_when_missing(self):
        article = self._create_article(thumbnail_url="")

        assign_default_thumbnail(article)
        article.refresh_from_db()

        self.assertEqual(
            article.thumbnail_url,
            "https://cdn.example.com/default.jpg",
        )

    @override_settings(NEWS_DEFAULT_IMAGE_URL="https://cdn.example.com/default.jpg")
    def test_does_not_override_existing_thumbnail(self):
        article = self._create_article(
            thumbnail_url="https://cdn.example.com/custom.jpg"
        )

        assign_default_thumbnail(article)
        article.refresh_from_db()

        self.assertEqual(
            article.thumbnail_url,
            "https://cdn.example.com/custom.jpg",
        )

    @override_settings(NEWS_DEFAULT_IMAGE_URL="")
    def test_returns_early_when_default_not_configured(self):
        article = self._create_article(thumbnail_url="")

        assign_default_thumbnail(article)
        article.refresh_from_db()

        self.assertEqual(article.thumbnail_url, "")
