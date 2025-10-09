from django.db import models


class DownloadLog(models.Model):
    """Persist individual chart download events."""

    username = models.CharField(max_length=255)
    chart_type = models.CharField(max_length=255)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "download_logs"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.username} - {self.chart_type} @ {self.timestamp.isoformat()}"
