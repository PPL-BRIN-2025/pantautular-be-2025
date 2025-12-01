from __future__ import annotations

from typing import Callable

from news_feature.models import NewsArticle
from news_feature.services.default_image import assign_default_thumbnail
from news_feature.services.normalization import NewsNormalizer, NewsPayload


class NewsArticleAssembler:
    """
    Responsible for instantiating and updating NewsArticle objects.
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
