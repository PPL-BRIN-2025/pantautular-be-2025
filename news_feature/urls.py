from django.urls import path

from news_feature.api import NewsArticleViewSet

app_name = "news_feature"

news_list = NewsArticleViewSet.as_view({"get": "list"})
news_detail = NewsArticleViewSet.as_view({"get": "retrieve"})

urlpatterns = [
    path("", news_list, name="news-list"),
    path("<uuid:pk>/", news_detail, name="news-detail"),
]
