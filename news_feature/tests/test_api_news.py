from datetime import datetime, timezone as dt_timezone
import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from pt_backend.models import Case, Disease, Location, News


class NewsApiTests(APITestCase):
    def setUp(self):
        self.case = self._create_case()
        self.article_recent = self._create_news(
            title="Latest policy update",
            type="Kurasi",
            portal="Kompas",
            content="Policy focus",
            date_published=datetime(2025, 2, 2, tzinfo=dt_timezone.utc),
            img_url="https://img/latest.jpg",
        )
        self.article_middle = self._create_news(
            title="Malaria outbreak",
            type="Health",
            portal="Detik",
            content="A malaria surge is ongoing",
            date_published=datetime(2025, 1, 15, tzinfo=dt_timezone.utc),
            img_url="",
        )
        self.article_old = self._create_news(
            title="Routine health bulletin",
            type="Kurasi",
            portal="Kompas",
            content="General updates",
            date_published=datetime(2025, 1, 1, tzinfo=dt_timezone.utc),
            img_url="",
        )
        self.list_url = reverse("news_feature:news-list")

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
            age=30,
            city="Jakarta",
            status=Case.STATUS_CHOICES[0][0],
            severity=Case.SEVERITY_CHOICES[0][0],
            disease=disease,
            location=location,
        )

    def _create_news(self, **overrides):
        base = {
            "portal": "Kompas",
            "title": "Base title",
            "type": "Nasional",
            "content": "Base summary",
            "url": f"https://example.com/{uuid.uuid4()}",
            "author": "Reporter",
            "date_published": datetime.now(dt_timezone.utc),
            "img_url": "",
            "case": self.case,
        }
        base.update(overrides)
        return News.objects.create(**base)

    def test_list_endpoint_returns_paginated_articles_ordered_by_published_at(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [item["title"] for item in response.data["data"]]
        self.assertEqual(
            titles,
            ["Latest policy update", "Malaria outbreak", "Routine health bulletin"],
        )
        self.assertEqual(response.data["total"], 3)
        self.assertEqual(response.data["page"], 1)
        self.assertEqual(response.data["pageSize"], 10)
        first = response.data["data"][0]
        self.assertEqual(first["curated_tags"], ["Kurasi"])

    def test_detail_endpoint_returns_article(self):
        url = reverse("news_feature:news-detail", args=[self.article_middle.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.article_middle.id))
        self.assertEqual(response.data["source_name"], "Detik")
        self.assertEqual(response.data["curated_tags"], ["Health"])

    def test_detail_endpoint_returns_404_for_missing_article(self):
        fake_id = "11111111-1111-1111-1111-111111111111"
        url = reverse("news_feature:news-detail", args=[fake_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filters_search_and_has_image(self):
        response = self.client.get(
            self.list_url,
            {
                "search": "policy",
                "has_image": "true",
            },
        )
        self.assertEqual(
            [item["id"] for item in response.data["data"]],
            [str(self.article_recent.id)],
        )

    def test_filters_by_tags_and_curated_only(self):
        response = self.client.get(
            self.list_url,
            {"tags": "Kurasi", "curated_only": "true"},
        )
        ids = [item["id"] for item in response.data["data"]]
        self.assertCountEqual(
            ids, [str(self.article_recent.id), str(self.article_old.id)]
        )

    def test_filters_by_date_range_and_source(self):
        response = self.client.get(
            self.list_url,
            {
                "source": "Detik",
                "from_date": datetime(2025, 1, 2, tzinfo=dt_timezone.utc).isoformat(),
                "to_date": datetime(2025, 1, 31, tzinfo=dt_timezone.utc).isoformat(),
            },
        )
        ids = [item["id"] for item in response.data["data"]]
        self.assertEqual(ids, [str(self.article_middle.id)])

    def test_api_prefix_aliases_are_available(self):
        for url in ("/api/news/", "/api/news", f"/api/news/{self.article_recent.id}/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_page_size_query_parameter_controls_output(self):
        response = self.client.get(self.list_url, {"page_size": 2})
        self.assertEqual(len(response.data["data"]), 2)
        self.assertEqual(response.data["pageSize"], 2)
