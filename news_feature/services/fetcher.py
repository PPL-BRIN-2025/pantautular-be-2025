"""
Backwards-compatible import surface for the refactored ingestion services.

Tests and legacy modules continue to import types from this module, while the
implementation has been split into dedicated modules that follow SOLID
principles (normalization, persistence, assembling, client/provider, ingestion).
"""

from news_feature.services.assemblers import NewsArticleAssembler
from news_feature.services.ingestor import (
    ArticlePersistenceExecutor,
    ArticlePlanBuilder,
    NewsIngestor,
    fetch_and_store_news,
)
from news_feature.services.normalization import NewsNormalizer, NewsPayload
from news_feature.services.persistence import (
    ArticlePersistencePlan,
    DjangoNewsArticleRepository,
    ExistingArticleIndex,
    NewsArticleRepository,
)
from news_feature.services.providers import ExternalNewsClient, NewsProvider

__all__ = [
    "ArticlePersistenceExecutor",
    "ArticlePlanBuilder",
    "ArticlePersistencePlan",
    "DjangoNewsArticleRepository",
    "ExistingArticleIndex",
    "ExternalNewsClient",
    "NewsArticleAssembler",
    "NewsArticleRepository",
    "NewsIngestor",
    "NewsNormalizer",
    "NewsPayload",
    "NewsProvider",
    "fetch_and_store_news",
]
