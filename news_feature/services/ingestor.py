from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable, List, Optional

from django.db import transaction

from news_feature.models import NewsArticle
from news_feature.services.assemblers import NewsArticleAssembler
from news_feature.services.normalization import NewsNormalizer, NewsPayload
from news_feature.services.persistence import (
    ArticlePersistencePlan,
    ExistingArticleIndex,
    DjangoNewsArticleRepository,
    NewsArticleRepository,
)
from news_feature.services.providers import ExternalNewsClient, NewsProvider

logger = logging.getLogger(__name__)


def fetch_and_store_news(provider: str = "default", client: Optional[ExternalNewsClient] = None) -> List[NewsArticle]:
    return NewsIngestor(client=client).fetch_and_store(provider=provider)


class ArticlePlanBuilder:
    """
    Separates the responsibility of matching payloads with persistence operations.
    """

    def __init__(self, assembler: NewsArticleAssembler):
        self.assembler = assembler

    def build(self, normalized: List[NewsPayload], existing: ExistingArticleIndex) -> ArticlePersistencePlan:
        plan = ArticlePersistencePlan.empty()
        for item in normalized:
            article = existing.match(item)
            if article:
                self.assembler.apply(article, item)
                plan.to_update.append(article)
                continue
            plan.to_create.append(self.assembler.build(item))
        return plan


class ArticlePersistenceExecutor:
    """
    Handles transaction boundaries for persisting ArticlePersistencePlan data.
    """

    def __init__(self, repository: NewsArticleRepository):
        self.repository = repository

    def persist(self, plan: ArticlePersistencePlan) -> List[NewsArticle]:
        if plan.is_empty():
            return []

        saved_articles: List[NewsArticle] = []
        with transaction.atomic():
            saved_articles.extend(self.repository.save_new(plan.to_create))
            saved_articles.extend(self.repository.update_existing(plan.to_update))
        return saved_articles


class NewsIngestor:
    """
    Coordinates fetching, normalization, plan building, and persistence.
    """

    def __init__(
        self,
        client: Optional[NewsProvider] = None,
        normalizer: Optional[NewsNormalizer] = None,
        repository: Optional[NewsArticleRepository] = None,
        assembler: Optional[NewsArticleAssembler] = None,
        plan_builder: Optional[ArticlePlanBuilder] = None,
        persister: Optional[ArticlePersistenceExecutor] = None,
    ):
        self.client = client or ExternalNewsClient()
        self.normalizer = normalizer or NewsNormalizer()
        self.repository = repository or DjangoNewsArticleRepository()
        self.assembler = assembler or NewsArticleAssembler()
        self.plan_builder = plan_builder or ArticlePlanBuilder(self.assembler)
        self.persister = persister or ArticlePersistenceExecutor(self.repository)

    def fetch_and_store(self, provider: str = "default") -> List[NewsArticle]:
        raw_items = self._safe_fetch(provider)
        normalized = self._normalize_items(raw_items)
        if not normalized:
            return []

        existing_index = self._build_existing_index(normalized)
        plan = self._split_articles(normalized, existing_index)
        return self._store_articles(plan)

    def _safe_fetch(self, provider: str) -> Iterable[dict]:
        try:
            return self.client.fetch(provider=provider)
        except Exception:
            logger.exception("Failed to fetch news articles from provider %s", provider)
            return []

    def _split_articles(
        self, normalized: List[NewsPayload], existing: ExistingArticleIndex
    ) -> ArticlePersistencePlan:
        return self.plan_builder.build(normalized, existing)

    def _build_article(self, payload: NewsPayload) -> NewsArticle:
        return self.assembler.build(payload)

    def _store_articles(self, plan: ArticlePersistencePlan) -> List[NewsArticle]:
        return self.persister.persist(plan)

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

    # Backwards-compatible helpers for older imports/tests.
    def normalize_items(self, raw_items: Iterable[dict]) -> List[NewsPayload]:  # pragma: no cover
        return self._normalize_items(raw_items)

    def normalize_item(self, item: dict) -> NewsPayload:  # pragma: no cover
        return self._normalize_item(item)

    def get_existing_articles(self, normalized_items: List[NewsPayload]) -> dict:  # pragma: no cover
        return self._get_existing_articles(normalized_items)

    def update_article_from_payload(self, article: NewsArticle, payload: NewsPayload) -> None:  # pragma: no cover
        return self._update_article_from_payload(article, payload)
