from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import datetime
from typing import Iterable, List, Optional

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news_feature.models import NewsArticle
from news_feature.services.default_image import assign_default_thumbnail


logger = logging.getLogger(__name__)


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
    client = client or ExternalNewsClient()

    try:
        raw_items = client.fetch(provider=provider)
    except Exception:  # pragma: no cover - defensive logging branch
        logger.exception("Failed to fetch news articles from provider %s", provider)
        return []

    normalized = _normalize_items(raw_items)
    if not normalized:
        return []

    existing = _get_existing_articles(normalized)
    to_create, to_update = _split_articles(normalized, existing)
    return _store_articles(to_create, to_update)


def _split_articles(normalized: List[dict], existing: dict) -> tuple[List[NewsArticle], List[NewsArticle]]:
    to_create: List[NewsArticle] = []
    to_update: List[NewsArticle] = []

    for item in normalized:
        article = _match_existing(existing, item)
        if article:
            _update_article_from_payload(article, item)
            to_update.append(article)
            continue

        to_create.append(_build_article(item))

    return to_create, to_update


def _build_article(payload: dict) -> NewsArticle:
    article = NewsArticle(
        title=payload["title"],
        summary=_coerce_text(payload["summary"]),
        source_url=payload["source_url"],
        source_name=payload["source_name"],
        thumbnail_url=_coerce_text(payload["thumbnail_url"]),
        published_at=payload["published_at"],
        external_id=_coerce_text(payload["external_id"]),
    )
    assign_default_thumbnail(article)
    return article


def _store_articles(to_create: List[NewsArticle], to_update: List[NewsArticle]) -> List[NewsArticle]:
    if not to_create and not to_update:
        return []

    saved_articles: List[NewsArticle] = []
    with transaction.atomic():
        saved_articles.extend(_save_new_articles(to_create))
        saved_articles.extend(_update_existing_articles(to_update))

    return saved_articles


def _save_new_articles(to_create: List[NewsArticle]) -> List[NewsArticle]:
    if not to_create:
        return []

    # Regular save keeps SQLite-based tests stable with the unique source_url constraint.
    for article in to_create:
        article.save()
    return list(to_create)


def _update_existing_articles(to_update: List[NewsArticle]) -> List[NewsArticle]:
    if not to_update:
        return []

    now = timezone.now()
    for article in to_update:
        if not _is_value_present(article.thumbnail_url):
            temp = NewsArticle(thumbnail_url=_coerce_text(article.thumbnail_url))
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
    return list(to_update)


def _normalize_items(raw_items: Iterable[dict]) -> List[dict]:
    seen = OrderedDict()
    for item in raw_items or []:
        try:
            normalized = _normalize_item(item)
        except ValueError as exc:
            logger.warning("Skipping invalid news payload: %s", exc)
            continue

        dedup_key = normalized["external_id"] or normalized["source_url"]
        if dedup_key in seen:
            continue
        seen[dedup_key] = normalized

    return list(seen.values())


def _normalize_item(item: dict) -> dict:
    title = (item.get("title") or item.get("headline") or "").strip()
    if not title:
        raise ValueError("title is required")

    source_url = (item.get("source_url") or item.get("url") or "").strip()
    if not source_url:
        raise ValueError("source_url is required")

    source_name = _extract_source_name(item)
    if not source_name:
        raise ValueError("source_name is required")

    published_at = _parse_datetime(
        item.get("published_at")
        or item.get("publishedAt")
        or item.get("date_published")
        or item.get("published")
    )
    if not published_at:
        raise ValueError("published_at is required")

    summary = _coerce_text(
        item.get("summary") or item.get("description") or item.get("content")
    )

    thumbnail = _coerce_text(
        item.get("thumbnail_url")
        or item.get("thumbnail")
        or item.get("image_url")
        or item.get("image")
    )

    external_id = item.get("external_id") or item.get("externalId") or item.get("id")
    if external_id is not None:
        external_id = str(external_id).strip() or None

    return {
        "title": title,
        "summary": summary,
        "source_url": source_url,
        "source_name": source_name,
        "thumbnail_url": thumbnail,
        "published_at": published_at,
        "external_id": _coerce_text(external_id),
    }


def _extract_source_name(item: dict) -> Optional[str]:
    source = item.get("source_name") or item.get("source")
    if isinstance(source, dict):
        return (source.get("name") or "").strip() or None
    if isinstance(source, str):
        return source.strip() or None
    return None


def _parse_datetime(value) -> Optional[datetime]:
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


def _get_existing_articles(normalized_items: List[dict]) -> dict:
    external_ids = [item["external_id"] for item in normalized_items if item["external_id"]]
    source_urls = [item["source_url"] for item in normalized_items]

    if not external_ids and not source_urls:
        return {"external": {}, "url": {}}

    query = Q()
    if external_ids:  # pragma: no branch
        query |= Q(external_id__in=external_ids)
    if source_urls:  # pragma: no branch
        query |= Q(source_url__in=source_urls)

    existing = NewsArticle.objects.filter(query)
    by_external = {}
    by_url = {}
    for article in existing:
        if article.external_id:
            by_external[article.external_id] = article
        by_url[article.source_url] = article

    return {"external": by_external, "url": by_url}


def _match_existing(existing: dict, item: dict) -> Optional[NewsArticle]:
    if item["external_id"]:
        article = existing["external"].get(item["external_id"])
        if article:
            return article

    return existing["url"].get(item["source_url"])


def _update_article_from_payload(article: NewsArticle, payload: dict) -> None:
    article.title = payload["title"]
    article.summary = _coerce_text(payload["summary"])
    article.source_url = payload["source_url"]
    article.source_name = payload["source_name"]
    article.published_at = payload["published_at"]
    thumbnail = _coerce_text(payload["thumbnail_url"])
    if _is_value_present(thumbnail):
        article.thumbnail_url = thumbnail
    article.external_id = _coerce_text(payload["external_id"])


def _is_value_present(value: Optional[str]) -> bool:
    if not value:
        return False
    return bool(str(value).strip())


def _coerce_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).strip()
