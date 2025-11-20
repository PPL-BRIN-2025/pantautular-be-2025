from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:  # pragma: no cover
    from news_feature.models import NewsArticle


def assign_default_thumbnail(article: "NewsArticle") -> None:
    """
    Ensure NewsArticle has a thumbnail, falling back to NEWS_DEFAULT_IMAGE_URL.
    """
    default_url = getattr(settings, "NEWS_DEFAULT_IMAGE_URL", "")
    if not default_url:
        return

    current_value = (getattr(article, "thumbnail_url", "") or "").strip()
    if current_value:
        return

    article.thumbnail_url = default_url

    should_save = getattr(article, "_state", None) and not article._state.adding
    if should_save:  # pragma: no branch
        article.save(update_fields=["thumbnail_url", "updated_at"])
