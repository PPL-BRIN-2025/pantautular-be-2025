from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.test import TestCase

from pt_backend.models import Case, News, User

from news_feature.management.commands.seed_news_articles import Command, SEED_USER_EMAIL


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

    def test_ensure_case_resets_non_placeholder_password(self):
        user = User.objects.create(
            email=SEED_USER_EMAIL,
            name="Seeder",
            role="CURATOR",
            password=make_password("not-placeholder"),
        )
        command = Command()

        command._ensure_case()

        user.refresh_from_db()
        self.assertTrue(user.password.startswith("!"))
