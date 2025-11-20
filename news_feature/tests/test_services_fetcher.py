from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import SimpleTestCase, TestCase, override_settings

from news_feature.models import NewsArticle
from news_feature.services.fetcher import (
    ExternalNewsClient,
    _extract_source_name,
    _get_existing_articles,
    _is_value_present,
    _normalize_item,
    _normalize_items,
    _parse_datetime as fetcher_parse_datetime,
    fetch_and_store_news,
)


def iso(dt: datetime) -> str:
    return dt.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.fetch_called_with = None

    def fetch(self, provider="default"):
        self.fetch_called_with = provider
        return self.payload


class FailingClient:
    def fetch(self, provider="default"):
        raise RuntimeError("network down")


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class DummySession:
    def __init__(self, payload):
        self.payload = payload
        self.called_with = None

    def get(self, url, **kwargs):
        self.called_with = (url, kwargs)
        return DummyResponse(self.payload)


@override_settings(NEWS_DEFAULT_IMAGE_URL="https://cdn.example.com/default.jpg")
class FetchAndStoreNewsTests(TestCase):
    def setUp(self):
        super().setUp()
        base = datetime(2025, 1, 1, tzinfo=dt_timezone.utc)
        self.payload = [
            {
                "id": "ext-1",
                "title": "Article 1",
                "summary": "Summary 1",
                "url": "https://example.com/a1",
                "source": {"name": "Kompas"},
                "published_at": iso(base),
                "thumbnail": "https://img/1.jpg",
            },
            {
                "id": "ext-2",
                "title": "Article 2",
                "summary": "Summary 2",
                "url": "https://example.com/a2",
                "source": {"name": "Detik"},
                "published_at": iso(base + timedelta(hours=2)),
                "thumbnail": None,
            },
        ]

    def test_successful_fetch_creates_articles_and_assigns_defaults(self):
        result = fetch_and_store_news(client=FakeClient(self.payload))

        self.assertEqual(len(result), 2)
        self.assertEqual(NewsArticle.objects.count(), 2)

        second = NewsArticle.objects.get(source_url="https://example.com/a2")
        self.assertEqual(second.thumbnail_url, "https://cdn.example.com/default.jpg")

    def test_existing_article_is_updated_instead_of_duplicated(self):
        existing = NewsArticle.objects.create(
            title="Old",
            summary="Old summary",
            source_url="https://example.com/a1",
            source_name="Old",
            thumbnail_url="https://img/old.jpg",
            published_at=datetime(2024, 12, 31, tzinfo=dt_timezone.utc),
            external_id="ext-1",
        )

        result = fetch_and_store_news(client=FakeClient(self.payload))

        self.assertEqual(len(result), 2)
        self.assertEqual(NewsArticle.objects.count(), 2)
        existing.refresh_from_db()
        self.assertEqual(existing.title, "Article 1")
        self.assertEqual(existing.source_name, "Kompas")

    def test_source_url_is_used_when_external_id_missing(self):
        existing = NewsArticle.objects.create(
            title="Old 2",
            summary="Old summary",
            source_url="https://example.com/a2",
            source_name="Old source",
            thumbnail_url="https://img/old2.jpg",
            published_at=datetime(2024, 12, 30, tzinfo=dt_timezone.utc),
            external_id="",
        )

        payload = [
            {
                "id": None,
                "title": "Updated title",
                "summary": "New summary",
                "url": "https://example.com/a2",
                "source": {"name": "Detik"},
                "published_at": iso(datetime(2025, 1, 5, tzinfo=dt_timezone.utc)),
            }
        ]

        fetch_and_store_news(client=FakeClient(payload))

        existing.refresh_from_db()
        self.assertEqual(existing.title, "Updated title")
        self.assertEqual(existing.source_name, "Detik")

    def test_invalid_items_are_skipped_and_do_not_block_others(self):
        bad_payload = [
            {"id": "missing-url", "title": "Bad article"},  # missing url/source/published_at
            {
                "id": "valid",
                "title": "Valid",
                "summary": "OK",
                "url": "https://example.com/good",
                "source": {"name": "Kompas"},
                "published_at": iso(datetime(2025, 1, 2, tzinfo=dt_timezone.utc)),
            },
        ]

        result = fetch_and_store_news(client=FakeClient(bad_payload))

        self.assertEqual(len(result), 1)
        self.assertEqual(NewsArticle.objects.count(), 1)

    def test_fetch_error_does_not_raise_and_returns_empty_list(self):
        result = fetch_and_store_news(client=FailingClient())

        self.assertEqual(result, [])
        self.assertEqual(NewsArticle.objects.count(), 0)

    def test_returns_empty_when_client_has_no_items(self):
        result = fetch_and_store_news(client=FakeClient([]))
        self.assertEqual(result, [])

    def test_update_assigns_thumbnail_when_missing(self):
        existing = NewsArticle.objects.create(
            title="Needs image",
            summary="Missing image",
            source_url="https://example.com/a3",
            source_name="Kompas",
            thumbnail_url="",
            published_at=datetime(2024, 12, 29, tzinfo=dt_timezone.utc),
            external_id="ext-3",
        )

        payload = [
            {
                "id": "ext-3",
                "title": "Updated",
                "summary": "Updated summary",
                "url": "https://example.com/a3",
                "source": {"name": "Kompas"},
                "published_at": iso(datetime(2025, 1, 3, tzinfo=dt_timezone.utc)),
                "thumbnail": "",
            }
        ]

        fetch_and_store_news(client=FakeClient(payload))

        existing.refresh_from_db()
        self.assertEqual(existing.thumbnail_url, "https://cdn.example.com/default.jpg")


class ExternalNewsClientTests(SimpleTestCase):
    def test_fetch_returns_empty_when_base_url_missing(self):
        client = ExternalNewsClient(session=DummySession([]))
        self.assertEqual(client.fetch(), [])

    @override_settings(
        NEWS_API_BASE_URL="https://api.example.com/news",
        NEWS_API_KEY="secret",
        NEWS_API_TIMEOUT=5,
    )
    def test_fetch_handles_list_payload(self):
        session = DummySession([{"title": "hello"}])
        client = ExternalNewsClient(session=session)

        data = client.fetch(provider="curated")

        self.assertEqual(data, [{"title": "hello"}])
        self.assertEqual(session.called_with[0], "https://api.example.com/news")
        headers = session.called_with[1]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer secret")

    @override_settings(NEWS_API_BASE_URL="https://api.example.com/news")
    def test_fetch_extracts_articles_from_dict_payload(self):
        payload = {"articles": [{"title": "dict"}]}
        session = DummySession(payload)
        client = ExternalNewsClient(session=session)

        self.assertEqual(client.fetch(), [{"title": "dict"}])

    @override_settings(NEWS_API_BASE_URL="https://api.example.com/news")
    def test_fetch_returns_empty_for_unexpected_payload(self):
        session = DummySession({"unexpected": True})
        client = ExternalNewsClient(session=session)

        self.assertEqual(client.fetch(), [])

    @override_settings(NEWS_API_BASE_URL="https://api.example.com/news")
    def test_fetch_handles_non_iterable_payload(self):
        session = DummySession(123)
        client = ExternalNewsClient(session=session)

        self.assertEqual(client.fetch(), [])


class FetcherHelperUnitTests(SimpleTestCase):
    def test_normalize_items_deduplicates_entries(self):
        payload = [
            {
                "title": "Title",
                "summary": "S",
                "url": "https://example.com/one",
                "source": {"name": "Kompas"},
                "published_at": iso(datetime(2025, 1, 1, tzinfo=dt_timezone.utc)),
                "thumbnail": "",
                "id": "dup",
            },
            {
                "title": "Title 2",
                "summary": "S2",
                "url": "https://example.com/one",
                "source": {"name": "Kompas"},
                "published_at": iso(datetime(2025, 1, 2, tzinfo=dt_timezone.utc)),
                "thumbnail": None,
                "id": "dup",
            },
        ]

        normalized = _normalize_items(payload)

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["title"], "Title")

    def test_normalize_item_validations(self):
        base = {
            "summary": "S",
            "url": "https://example.com",
            "source": {"name": "Kompas"},
            "published_at": iso(datetime(2025, 1, 1, tzinfo=dt_timezone.utc)),
        }

        with self.assertRaisesMessage(ValueError, "title is required"):
            _normalize_item({**base, "title": ""})

        with self.assertRaisesMessage(ValueError, "source_url is required"):
            _normalize_item(
                {
                    **base,
                    "title": "Title",
                    "url": "",
                }
            )

        with self.assertRaisesMessage(ValueError, "source_name is required"):
            _normalize_item(
                {
                    **base,
                    "title": "Title",
                    "source": "",
                }
            )

        with self.assertRaisesMessage(ValueError, "published_at is required"):
            _normalize_item(
                {
                    **base,
                    "title": "Title",
                    "published_at": None,
                }
            )

    def test_extract_source_name_variants(self):
        self.assertEqual(
            _extract_source_name({"source": {"name": "Kompas"}}),
            "Kompas",
        )
        self.assertEqual(_extract_source_name({"source_name": " Detik "}), "Detik")
        self.assertIsNone(_extract_source_name({"source": 123}))

    def test_parse_datetime_variants(self):
        aware = datetime(2025, 1, 1, tzinfo=dt_timezone.utc)
        self.assertEqual(fetcher_parse_datetime(aware), aware)

        naive_str = "2025-01-01T12:00:00"
        converted = fetcher_parse_datetime(naive_str)
        self.assertIsNotNone(converted.tzinfo)

        self.assertIsNone(fetcher_parse_datetime("invalid"))
        self.assertIsNone(fetcher_parse_datetime(None))

    def test_is_value_present(self):
        self.assertFalse(_is_value_present(""))
        self.assertTrue(_is_value_present(" data "))


class GetExistingArticlesTests(TestCase):
    def test_returns_empty_mapping_when_no_identifiers(self):
        self.assertEqual(
            _get_existing_articles([]),
            {"external": {}, "url": {}},
        )

    def test_returns_existing_records(self):
        article = NewsArticle.objects.create(
            title="Existing",
            summary="S",
            source_url="https://example.com/existing",
            source_name="Kompas",
            thumbnail_url="",
            published_at=datetime(2025, 1, 1, tzinfo=dt_timezone.utc),
            external_id="ext-existing",
        )

        result = _get_existing_articles(
            [
                {
                    "external_id": "ext-existing",
                    "source_url": "https://example.com/existing",
                }
            ]
        )

        self.assertEqual(result["external"]["ext-existing"], article)
        self.assertEqual(result["url"]["https://example.com/existing"], article)
