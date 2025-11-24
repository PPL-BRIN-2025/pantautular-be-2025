from django.conf import settings
from rest_framework import serializers

from pt_backend.models import News

from news_feature.constants import CURATED_TYPE_KEYWORDS


class NewsArticleSerializer(serializers.ModelSerializer):
    summary = serializers.CharField(source="content")
    source_name = serializers.CharField(source="portal")
    source_url = serializers.CharField(source="url")
    thumbnail_url = serializers.SerializerMethodField()
    published_at = serializers.DateTimeField(source="date_published")
    curated_tags = serializers.SerializerMethodField()
    is_curated = serializers.SerializerMethodField()

    class Meta:
        model = News
        fields = [
            "id",
            "title",
            "summary",
            "source_name",
            "source_url",
            "thumbnail_url",
            "published_at",
            "is_curated",
            "curated_tags",
        ]
        read_only_fields = fields

    def get_thumbnail_url(self, obj: News):
        url = (obj.img_url or "").strip()
        if url:
            return url
        return getattr(settings, "NEWS_DEFAULT_IMAGE_URL", "") or None

    def get_curated_tags(self, obj: News):
        value = (obj.type or "").strip()
        return [value] if value else []

    def get_is_curated(self, obj: News) -> bool:
        tag_value = (obj.type or "").strip().lower()
        return tag_value in CURATED_TYPE_KEYWORDS
