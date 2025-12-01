from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Union

from django.db.models import Q, QuerySet

from news_feature.constants import CURATED_TYPE_KEYWORDS
from news_feature.services.normalization import NewsNormalizer


@dataclass(frozen=True)
class NewsFilterParams:
    search: str = ""
    sources: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    curated_only: bool = False
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    has_image: bool = False

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]] = None) -> "NewsFilterParams":
        data = data or {}
        return cls(
            search=_clean_str(_get_param(data, "search")),
            sources=tuple(_parse_csv(_get_param(data, "source"))),
            tags=tuple(_parse_csv(_get_param(data, "tags"))),
            curated_only=_to_bool(_get_param(data, "curated_only")),
            from_date=_parse_datetime(_get_param(data, "from_date")),
            to_date=_parse_datetime(_get_param(data, "to_date")),
            has_image=_to_bool(_get_param(data, "has_image")),
        )


def build_filter_params(data: Optional[Mapping[str, Any]] = None) -> NewsFilterParams:
    return NewsFilterParams.from_dict(data)


def filter_news(qs: QuerySet, params: Union[NewsFilterParams, Mapping[str, Any], None]) -> QuerySet:
    """
    Apply query-parameter-driven filters to a NewsArticle queryset.
    """
    parsed = params if isinstance(params, NewsFilterParams) else NewsFilterParams.from_dict(params)

    if parsed.search:
        qs = qs.filter(Q(title__icontains=parsed.search) | Q(content__icontains=parsed.search))

    if parsed.sources:
        qs = qs.filter(portal__in=parsed.sources)

    if parsed.tags:
        tag_filter = Q()
        for tag in parsed.tags:
            tag_filter |= Q(type__iexact=tag)
        qs = qs.filter(tag_filter)

    if parsed.curated_only:
        curated_filter = Q()
        for keyword in CURATED_TYPE_KEYWORDS:
            curated_filter |= Q(type__iexact=keyword)
        qs = qs.filter(curated_filter)

    if parsed.from_date:
        qs = qs.filter(date_published__gte=parsed.from_date)

    if parsed.to_date:
        qs = qs.filter(date_published__lte=parsed.to_date)

    if parsed.has_image:
        qs = qs.exclude(Q(img_url__isnull=True) | Q(img_url__exact=""))

    return qs


def _parse_csv(value: Optional[Union[str, Sequence[str]]]) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        iterable: Iterable[str] = value
    else:
        iterable = str(value).split(",")
    parsed = [item.strip() for item in iterable if item and item.strip()]
    return parsed


def _parse_datetime(value) -> Optional[datetime]:
    return NewsNormalizer.parse_datetime(value)


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


def _get_param(data: Mapping[str, Any], key: str) -> Any:
    getter = getattr(data, "getlist", None)
    if callable(getter):
        values = getter(key)
        if not values:
            return None
        if len(values) == 1:
            return values[0]
        return values
    return data.get(key)
