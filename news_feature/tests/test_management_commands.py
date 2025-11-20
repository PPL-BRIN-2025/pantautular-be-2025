from django.core.management import call_command
from django.test import TestCase

from pt_backend.models import Case, News


class SeedNewsArticlesCommandTests(TestCase):
    def test_seed_command_creates_sample_articles_once(self):
        call_command("seed_news_articles")

        self.assertEqual(News.objects.count(), 3)
        article = News.objects.get(url="https://news.example.com/detik/update-dbd")
        self.assertEqual(article.portal, "Detik")
        self.assertTrue(Case.objects.filter(id="00000000-0000-0000-0000-00000000feed").exists())

        call_command("seed_news_articles")
        self.assertEqual(
            News.objects.count(),
            3,
            "Command should be idempotent on repeated runs.",
        )
