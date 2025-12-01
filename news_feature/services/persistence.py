from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, List, Optional, Protocol

from django.db.models import Q
from django.utils import timezone

from news_feature.models import NewsArticle
from news_feature.services.default_image import assign_default_thumbnail
from news_feature.services.normalization import NewsNormalizer, NewsPayload


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


class NewsArticleRepository(Protocol):
    def build_index(self, normalized_items: Iterable[NewsPayload]) -> ExistingArticleIndex:  # pragma: no cover - interface
        ...

    def save_new(self, articles: Iterable[NewsArticle]) -> List[NewsArticle]:  # pragma: no cover - interface
        ...

    def update_existing(self, articles: Iterable[NewsArticle]) -> List[NewsArticle]:  # pragma: no cover - interface
        ...


class DjangoNewsArticleRepository:
    """
    Encapsulates NewsArticle ORM interactions.
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
