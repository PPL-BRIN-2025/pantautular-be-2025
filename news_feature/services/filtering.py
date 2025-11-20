from __future__ import annotations

from typing import Iterable, List, Optional

from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news_feature.constants import CURATED_TYPE_KEYWORDS

def filter_news(qs: QuerySet, params: dict) -> QuerySet:
    """
    Apply query-parameter-driven filters to a NewsArticle queryset.
    """
    search_term = _clean_str(params.get("search"))
    if search_term:
        qs = qs.filter(
            Q(title__icontains=search_term) | Q(content__icontains=search_term)
        )

    sources = _parse_csv(params.get("source"))
    if sources:
        qs = qs.filter(portal__in=sources)

    tags = _parse_csv(params.get("tags"))
    if tags:
        tag_filter = Q()
        for tag in tags:
            tag_filter |= Q(type__iexact=tag)
        qs = qs.filter(tag_filter)

    if _to_bool(params.get("curated_only")):
        curated_filter = Q()
        for keyword in CURATED_TYPE_KEYWORDS:
            curated_filter |= Q(type__iexact=keyword)
        qs = qs.filter(curated_filter)

    from_date = _parse_datetime(params.get("from_date"))
    if from_date:
        qs = qs.filter(date_published__gte=from_date)

    to_date = _parse_datetime(params.get("to_date"))
    if to_date:
        qs = qs.filter(date_published__lte=to_date)

    if _to_bool(params.get("has_image")):
        qs = qs.exclude(Q(img_url__isnull=True) | Q(img_url__exact=""))

    return qs


def _parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        iterable: Iterable[str] = value
    else:
        iterable = str(value).split(",")
    parsed = [item.strip() for item in iterable if item and item.strip()]
    return parsed


def _parse_datetime(value) -> Optional[timezone.datetime]:
    if isinstance(value, timezone.datetime):
        dt = value
    elif value:
        dt = parse_datetime(str(value))
    else:
        return None

    if dt is None:
        return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _clean_str(value: Optional[str]) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()
