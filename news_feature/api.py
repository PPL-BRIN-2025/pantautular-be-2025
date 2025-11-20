from __future__ import annotations

from rest_framework import pagination, viewsets
from rest_framework.response import Response

from pt_backend.models import News

from news_feature.serializers import NewsArticleSerializer
from news_feature.services.filtering import filter_news


class NewsPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "data": data,
                "page": self.page.number,
                "pageSize": self.get_page_size(self.request) or self.page_size,
                "total": self.page.paginator.count,
            }
        )


class NewsArticleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NewsArticleSerializer
    pagination_class = NewsPagination

    def get_queryset(self):
        base_qs = News.objects.all().order_by("-date_published")
        params = {
            "search": self.request.query_params.get("search"),
            "source": self.request.query_params.get("source"),
            "tags": self.request.query_params.get("tags"),
            "curated_only": self.request.query_params.get("curated_only"),
            "from_date": self.request.query_params.get("from_date"),
            "to_date": self.request.query_params.get("to_date"),
            "has_image": self.request.query_params.get("has_image"),
        }
        return filter_news(base_qs, params)
