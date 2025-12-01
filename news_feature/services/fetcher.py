from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, List, Optional, Protocol

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news_feature.models import NewsArticle
from news_feature.services.default_image import assign_default_thumbnail


logger = logging.getLogger(__name__)


class NewsProvider(Protocol):
    def fetch(self, provider: str = "default") -> list:  # pragma: no cover - Protocol contract
        ...


@dataclass(frozen=True)
class NewsPayload:
    title: str
    summary: str
    source_url: str
    source_name: str
    thumbnail_url: str
    published_at: datetime
    external_id: str


@dataclass
class ArticlePersistencePlan:
    to_create: List[NewsArticle] = field(default_factory=list)
    to_update: List[NewsArticle] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "ArticlePersistencePlan":
        return cls()

    def is_empty(self) -> bool:
        return not self.to_create and not self.to_update


@dataclass
class ExistingArticleIndex:
    by_external: dict[str, NewsArticle] = field(default_factory=dict)
    by_url: dict[str, NewsArticle] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "ExistingArticleIndex":
        return cls()

    def match(self, payload: NewsPayload) -> Optional[NewsArticle]:
        if payload.external_id:
            article = self.by_external.get(payload.external_id)
            if article:
                return article

        return self.by_url.get(payload.source_url)

    def as_dict(self) -> dict:
        return {"external": self.by_external, "url": self.by_url}


class NewsNormalizer:
    """
    Normalizes raw provider payloads into typed value objects.
    """

    def normalize_items(self, raw_items: Iterable[dict]) -> List[NewsPayload]:
        seen: OrderedDict[str, NewsPayload] = OrderedDict()
        for item in raw_items or []:
            try:
                normalized = self.normalize_item(item)
            except ValueError as exc:
                logger.warning("Skipping invalid news payload: %s", exc)
                continue

            dedup_key = normalized.external_id or normalized.source_url
            if dedup_key in seen:
                continue
            seen[dedup_key] = normalized

        return list(seen.values())

    def normalize_item(self, item: dict) -> NewsPayload:
        title = self.coerce_text(item.get("title") or item.get("headline"))
        if not title:
            raise ValueError("title is required")

        source_url = self.coerce_text(item.get("source_url") or item.get("url"))
        if not source_url:
            raise ValueError("source_url is required")

        source_name = self.extract_source_name(item)
        if not source_name:
            raise ValueError("source_name is required")

        published_at = self.parse_datetime(
            item.get("published_at")
            or item.get("publishedAt")
            or item.get("date_published")
            or item.get("published")
        )
        if not published_at:
            raise ValueError("published_at is required")

        summary = self.coerce_text(
            item.get("summary") or item.get("description") or item.get("content")
        )

        thumbnail = self.coerce_text(
            item.get("thumbnail_url")
            or item.get("thumbnail")
            or item.get("image_url")
            or item.get("image")
        )

        external_id = self.coerce_optional_text(
            item.get("external_id") or item.get("externalId") or item.get("id")
        )

        return NewsPayload(
            title=title,
            summary=summary,
            source_url=source_url,
            source_name=source_name,
            thumbnail_url=thumbnail,
            published_at=published_at,
            external_id=external_id,
        )

    def extract_source_name(self, item: dict) -> Optional[str]:
        source = item.get("source_name") or item.get("source")
        if isinstance(source, dict):
            return (source.get("name") or "").strip() or None
        if isinstance(source, str):
            return source.strip() or None
        return None

    @staticmethod
    def parse_datetime(value) -> Optional[datetime]:
        if not value:
            return None

        if isinstance(value, datetime):
            dt = value
        else:
            dt = parse_datetime(value)

        if dt is None:
            return None

        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())

        return dt

    @staticmethod
    def is_value_present(value: Optional[str]) -> bool:
        if not value:
            return False
        return bool(str(value).strip())

    @staticmethod
    def coerce_text(value: Optional[str]) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def coerce_optional_text(value: Optional[str]) -> str:
        # Optional variant keeps the same contract but delegates to avoid divergent trimming logic.
        return NewsNormalizer.coerce_text(value)


class NewsArticleAssembler:
    """
    Responsible for translating normalized payloads into NewsArticle instances.
    """

    def __init__(self, thumbnail_assigner: Callable[[NewsArticle], None] = assign_default_thumbnail):
        self.thumbnail_assigner = thumbnail_assigner

    def build(self, payload: NewsPayload) -> NewsArticle:
        article = NewsArticle(
            title=payload.title,
            summary=payload.summary,
            source_url=payload.source_url,
            source_name=payload.source_name,
            thumbnail_url=payload.thumbnail_url,
            published_at=payload.published_at,
            external_id=payload.external_id,
        )
        self.thumbnail_assigner(article)
        return article

    def apply(self, article: NewsArticle, payload: NewsPayload) -> None:
        article.title = payload.title
        article.summary = payload.summary
        article.source_url = payload.source_url
        article.source_name = payload.source_name
        article.published_at = payload.published_at
        if NewsNormalizer.is_value_present(payload.thumbnail_url):
            article.thumbnail_url = payload.thumbnail_url
        article.external_id = payload.external_id


class NewsArticleRepository(Protocol):
    def build_index(self, normalized_items: Iterable[NewsPayload]) -> ExistingArticleIndex:  # pragma: no cover - interface
        ...

    def save_new(self, articles: Iterable[NewsArticle]) -> List[NewsArticle]:  # pragma: no cover - interface
        ...

    def update_existing(self, articles: Iterable[NewsArticle]) -> List[NewsArticle]:  # pragma: no cover - interface
        ...


class DjangoNewsArticleRepository:
    """
    Repository encapsulating all NewsArticle persistence details.
    """

    def __init__(self, now_provider: Callable[[], datetime] = timezone.now):
        self._now_provider = now_provider

    def build_index(self, normalized_items: Iterable[NewsPayload]) -> ExistingArticleIndex:
        items = list(normalized_items)
        external_ids = [item.external_id for item in items if item.external_id]
        source_urls = [item.source_url for item in items]

        if not external_ids and not source_urls:
            return ExistingArticleIndex.empty()

        query = Q()
        if external_ids:  # pragma: no branch
            query |= Q(external_id__in=external_ids)
        if source_urls:  # pragma: no branch
            query |= Q(source_url__in=source_urls)

        existing = NewsArticle.objects.filter(query)
        index = ExistingArticleIndex()
        for article in existing:
            if article.external_id:
                index.by_external[article.external_id] = article
            index.by_url[article.source_url] = article

        return index

    def save_new(self, articles: Iterable[NewsArticle]) -> List[NewsArticle]:
        to_create = list(articles)
        if not to_create:
            return []

        # Regular save keeps SQLite-based tests stable with the unique source_url constraint.
        for article in to_create:
            article.save()
        return to_create

    def update_existing(self, articles: Iterable[NewsArticle]) -> List[NewsArticle]:
        to_update = list(articles)
        if not to_update:
            return []

        now = self._now_provider()
        for article in to_update:
            if not NewsNormalizer.is_value_present(article.thumbnail_url):
                temp = NewsArticle(thumbnail_url=NewsNormalizer.coerce_optional_text(article.thumbnail_url))
                assign_default_thumbnail(temp)
                article.thumbnail_url = temp.thumbnail_url
            article.updated_at = now

        NewsArticle.objects.bulk_update(
            to_update,
            [
                "title",
                "summary",
                "source_url",
                "source_name",
                "thumbnail_url",
                "published_at",
                "external_id",
                "updated_at",
            ],
        )
        return to_update


class ExternalNewsClient:
    """
    Small HTTP client wrapper so the fetch logic stays easy to mock in tests.
    """

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.base_url = getattr(settings, "NEWS_API_BASE_URL", "")
        self.api_key = getattr(settings, "NEWS_API_KEY", "")
        self.timeout = getattr(settings, "NEWS_API_TIMEOUT", 10)

    def fetch(self, provider: str = "default") -> list:
        if not self.base_url:
            logger.warning("NEWS_API_BASE_URL is not configured; skipping fetch.")
            return []

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        params = {"provider": provider} if provider else {}

        response = self.session.get(
            self.base_url,
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            for key in ("articles", "data", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value

        logger.warning("Unexpected payload from news API: %s", type(payload))
        return []


def fetch_and_store_news(provider: str = "default", client: Optional[ExternalNewsClient] = None) -> List[NewsArticle]:
    return NewsIngestor(client=client).fetch_and_store(provider=provider)


class NewsIngestor:
    """
    Coordinates fetching, normalization, and persistence for third-party news data.
    """

    def __init__(
        self,
        client: Optional[NewsProvider] = None,
        normalizer: Optional[NewsNormalizer] = None,
        repository: Optional[NewsArticleRepository] = None,
        assembler: Optional[NewsArticleAssembler] = None,
    ):
        self.client = client or ExternalNewsClient()
        self.normalizer = normalizer or NewsNormalizer()
        self.repository = repository or DjangoNewsArticleRepository()
        self.assembler = assembler or NewsArticleAssembler()

    def fetch_and_store(self, provider: str = "default") -> List[NewsArticle]:
        try:
            raw_items = self.client.fetch(provider=provider)
        except Exception:
            logger.exception("Failed to fetch news articles from provider %s", provider)
            return []

        normalized = self._normalize_items(raw_items)
        if not normalized:
            return []

        existing_index = self._build_existing_index(normalized)
        plan = self._split_articles(normalized, existing_index)
        return self._store_articles(plan)

    def _split_articles(
        self, normalized: List[NewsPayload], existing: ExistingArticleIndex
    ) -> ArticlePersistencePlan:
        plan = ArticlePersistencePlan.empty()
        for item in normalized:
            article = self._match_existing(existing, item)
            if article:
                self._update_article_from_payload(article, item)
                plan.to_update.append(article)
                continue

            plan.to_create.append(self._build_article(item))

        return plan

    def _build_article(self, payload: NewsPayload) -> NewsArticle:
        return self.assembler.build(payload)

    def _store_articles(self, plan: ArticlePersistencePlan) -> List[NewsArticle]:
        if plan.is_empty():
            return []

        saved_articles: List[NewsArticle] = []
        with transaction.atomic():
            saved_articles.extend(self._save_new_articles(plan.to_create))
            saved_articles.extend(self._update_existing_articles(plan.to_update))

        return saved_articles

    def _save_new_articles(self, to_create: List[NewsArticle]) -> List[NewsArticle]:
        return self.repository.save_new(to_create)

    def _update_existing_articles(self, to_update: List[NewsArticle]) -> List[NewsArticle]:
        return self.repository.update_existing(to_update)

    def _normalize_items(self, raw_items: Iterable[dict]) -> List[NewsPayload]:
        return self.normalizer.normalize_items(raw_items)

    def _normalize_item(self, item: dict) -> NewsPayload:
        return self.normalizer.normalize_item(item)

    def _extract_source_name(self, item: dict) -> Optional[str]:
        return self.normalizer.extract_source_name(item)

    @staticmethod
    def _parse_datetime(value) -> Optional[datetime]:
        return NewsNormalizer.parse_datetime(value)

    def _build_existing_index(self, normalized_items: List[NewsPayload]) -> ExistingArticleIndex:
        return self.repository.build_index(normalized_items)

    def _get_existing_articles(self, normalized_items: List[NewsPayload]) -> dict:
        return self._build_existing_index(normalized_items).as_dict()

    def _match_existing(self, existing: dict, item: NewsPayload) -> Optional[NewsArticle]:
        if isinstance(existing, ExistingArticleIndex):
            return existing.match(item)

        if item.external_id:
            article = existing.get("external", {}).get(item.external_id)
            if article:
                return article

        return existing.get("url", {}).get(item.source_url)

    def _update_article_from_payload(self, article: NewsArticle, payload: NewsPayload) -> None:
        self.assembler.apply(article, payload)

    @staticmethod
    def _is_value_present(value: Optional[str]) -> bool:
        return NewsNormalizer.is_value_present(value)

    @staticmethod
    def _coerce_text(value: Optional[str]) -> str:
        return NewsNormalizer.coerce_text(value)

    @staticmethod
    def _coerce_optional_text(value: Optional[str]) -> str:
        return NewsNormalizer.coerce_optional_text(value)

    # Legacy helpers retained for backwards compatibility with existing imports/tests.
    def normalize_items(self, raw_items: Iterable[dict]) -> List[NewsPayload]:  # pragma: no cover - thin wrapper
        return self._normalize_items(raw_items)

    def normalize_item(self, item: dict) -> NewsPayload:  # pragma: no cover - thin wrapper
        return self._normalize_item(item)

    def get_existing_articles(self, normalized_items: List[NewsPayload]) -> dict:  # pragma: no cover - thin wrapper
        return self._get_existing_articles(normalized_items)

    def update_article_from_payload(self, article: NewsArticle, payload: NewsPayload) -> None:  # pragma: no cover
        return self._update_article_from_payload(article, payload)

