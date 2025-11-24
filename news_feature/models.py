import uuid

from django.db import models


class CuratedTag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class NewsArticle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=500)
    summary = models.TextField(blank=True, default="")
    source_url = models.URLField(unique=True)
    source_name = models.CharField(max_length=255, db_index=True)
    thumbnail_url = models.URLField(blank=True, default="")
    published_at = models.DateTimeField(db_index=True)
    is_curated = models.BooleanField(default=False, db_index=True)
    curated_tags = models.ManyToManyField(
        CuratedTag,
        related_name="articles",
        blank=True,
    )
    curator_note = models.TextField(blank=True, default="")
    external_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-published_at", "-created_at")

    def __str__(self) -> str:
        return self.title
