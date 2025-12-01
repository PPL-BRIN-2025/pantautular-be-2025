from __future__ import annotations

from rest_framework import pagination, viewsets
from rest_framework.response import Response

from pt_backend.models import News

from news_feature.serializers import NewsArticleSerializer
from news_feature.services.filtering import build_filter_params, filter_news


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
        params = build_filter_params(self.request.query_params)
        return filter_news(base_qs, params)
