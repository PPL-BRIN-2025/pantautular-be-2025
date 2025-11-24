from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from news_feature.models import CuratedTag, NewsArticle


class NewsArticleModelTests(TestCase):
    def _article_defaults(self):
        return {
            "title": "Sample title",
            "summary": "Summary text",
            "source_url": "https://example.com/article-1",
            "source_name": "Example Source",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "published_at": timezone.now(),
            "external_id": "external-1",
        }

    def test_create_news_article_with_minimum_fields(self):
        article = NewsArticle.objects.create(**self._article_defaults())

        self.assertIsNotNone(article.id)
        self.assertEqual(article.title, "Sample title")
        self.assertEqual(article.summary, "Summary text")
        self.assertEqual(article.source_name, "Example Source")
        self.assertFalse(article.is_curated)
        self.assertIsNotNone(article.created_at)
        self.assertIsNotNone(article.updated_at)

    def test_source_url_must_be_unique(self):
        NewsArticle.objects.create(**self._article_defaults())
        with self.assertRaises(IntegrityError):
            NewsArticle.objects.create(**self._article_defaults())

    def test_curated_tags_relationship_returns_names(self):
        article = NewsArticle.objects.create(**self._article_defaults())
        tag_a = CuratedTag.objects.create(name="Epidemiology")
        tag_b = CuratedTag.objects.create(name="Prevention")

        article.curated_tags.add(tag_a, tag_b)

        self.assertCountEqual(
            list(article.curated_tags.values_list("name", flat=True)),
            ["Epidemiology", "Prevention"],
        )

    def test_string_representations(self):
        tag = CuratedTag.objects.create(name="Policy")
        article = NewsArticle.objects.create(**self._article_defaults())

        self.assertEqual(str(tag), "Policy")
        self.assertEqual(str(article), "Sample title")

    def test_expected_indexes_are_configured(self):
        field_names = {
            "published_at",
            "is_curated",
            "source_name",
            "external_id",
        }

        for field_name in field_names:
            field = NewsArticle._meta.get_field(field_name)
            self.assertTrue(
                field.db_index,
                f"{field_name} should be indexed for faster filtering",
            )
