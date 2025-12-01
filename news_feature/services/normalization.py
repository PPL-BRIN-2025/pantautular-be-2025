from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NewsPayload:
    title: str
    summary: str
    source_url: str
    source_name: str
    thumbnail_url: str
    published_at: datetime
    external_id: str


class NewsNormalizer:
    """
    Converts unstructured provider payloads into NewsPayload objects.
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
        # Optional variant shares the trimming logic but preserves the optional contract.
        return NewsNormalizer.coerce_text(value)
