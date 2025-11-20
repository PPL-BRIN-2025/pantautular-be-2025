from datetime import datetime, timezone as dt_timezone
import uuid

from django.test import SimpleTestCase, TestCase

from pt_backend.models import Case, Disease, Location, News

from news_feature.services.filtering import (
    filter_news,
    _parse_csv,
    _parse_datetime,
    _to_bool,
)


class FilterNewsTests(TestCase):
    def setUp(self):
        self.case = self._create_case()
        self.article_1 = self._create_article(
            title="Malaria Outbreak in Jakarta",
            type="Kurasi",
            portal="Kompas",
            content="Cases up this month",
            date_published=datetime(2025, 1, 1, tzinfo=dt_timezone.utc),
            img_url="https://img/1.jpg",
        )
        self.article_2 = self._create_article(
            title="Dengue prevention tips",
            type="Health",
            portal="Detik",
            content="How to manage mosquitoes",
            date_published=datetime(2025, 1, 10, tzinfo=dt_timezone.utc),
            img_url="",
        )
        self.article_3 = self._create_article(
            title="Policy update on food safety",
            type="Kurasi",
            portal="Kompas",
            content="Government releases new policy",
            date_published=datetime(2025, 2, 1, tzinfo=dt_timezone.utc),
            img_url="",
        )

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
            age=20,
            city="Jakarta",
            status=Case.STATUS_CHOICES[0][0],
            severity=Case.SEVERITY_CHOICES[0][0],
            disease=disease,
            location=location,
        )

    def _create_article(self, **overrides):
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

    def test_search_filters_by_title_and_summary(self):
        qs = filter_news(News.objects.all(), {"search": "malaria"}).order_by("id")
        self.assertEqual(list(qs), [self.article_1])

        qs = filter_news(News.objects.all(), {"search": "mosquitoes"}).order_by("id")
        self.assertEqual(list(qs), [self.article_2])

    def test_source_filter_accepts_csv(self):
        qs = filter_news(News.objects.all(), {"source": "Kompas"})
        self.assertCountEqual(qs, [self.article_1, self.article_3])

        qs = filter_news(News.objects.all(), {"source": "Kompas,Detik"})
        self.assertCountEqual(qs, [self.article_1, self.article_2, self.article_3])

    def test_tag_filter_matches_any_tag(self):
        qs = filter_news(News.objects.all(), {"tags": "health"})
        self.assertCountEqual(qs, [self.article_2])

        qs = filter_news(News.objects.all(), {"tags": "kurasi"})
        self.assertCountEqual(qs, [self.article_1, self.article_3])

    def test_curated_only_flag(self):
        qs = filter_news(News.objects.all(), {"curated_only": True})
        self.assertCountEqual(qs, [self.article_1, self.article_3])

    def test_date_range_filters(self):
        params = {
            "from_date": (datetime(2025, 1, 15, tzinfo=dt_timezone.utc)).isoformat(),
            "to_date": (datetime(2025, 2, 2, tzinfo=dt_timezone.utc)).isoformat(),
        }
        qs = filter_news(News.objects.all(), params)
        self.assertCountEqual(qs, [self.article_3])

    def test_has_image_filter(self):
        qs = filter_news(News.objects.all(), {"has_image": True})
        self.assertCountEqual(qs, [self.article_1])

    def test_combination_of_filters(self):
        params = {
            "curated_only": True,
            "source": "Kompas",
            "tags": "Kurasi",
            "from_date": datetime(2025, 2, 1, tzinfo=dt_timezone.utc).isoformat(),
        }
        qs = filter_news(News.objects.all(), params)
        self.assertCountEqual(qs, [self.article_3])


class FilterHelperTests(SimpleTestCase):
    def test_parse_csv_handles_lists(self):
        self.assertEqual(_parse_csv(["Kompas", ""]), ["Kompas"])
        self.assertEqual(_parse_csv(" Kompas , Detik "), ["Kompas", "Detik"])

    def test_parse_datetime_variants(self):
        aware = datetime(2025, 1, 1, tzinfo=dt_timezone.utc)
        self.assertEqual(_parse_datetime(aware), aware)
        naive = datetime(2025, 1, 1, 12, 0, 0)
        converted = _parse_datetime(naive.isoformat())
        self.assertIsNotNone(converted.tzinfo)
        self.assertEqual(
            converted.utcoffset(),
            dt_timezone.utc.utcoffset(datetime.now(dt_timezone.utc)),
        )
        self.assertIsNone(_parse_datetime("invalid"))
        self.assertIsNone(_parse_datetime(None))

    def test_to_bool_handles_various_inputs(self):
        self.assertTrue(_to_bool("TRUE"))
        self.assertFalse(_to_bool(None))
        self.assertTrue(_to_bool(5))
        self.assertFalse(_to_bool(0))
