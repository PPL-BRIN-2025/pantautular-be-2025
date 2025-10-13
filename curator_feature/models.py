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


class DashboardDownloadEvent(models.Model):
    """Persistent log for dashboard image downloads."""

    class Metric(models.TextChoices):
        TOTAL_CASES = "jumlah_kasus", "Jumlah Kasus"
        PREVALENCE = "estimasi_prevalensi", "Estimasi Prevalensi"
        AGE = "usia", "Usia"
        GENDER = "jenis_kelamin", "Jenis Kelamin"
        CASE_LEVEL = "tingkat_kasus", "Tingkat Kasus"
        NEWS_SOURCE = "distribusi_sumber_berita", "Distribusi Sumber Berita"

    class FileFormat(models.TextChoices):
        PNG = "png", "PNG"
        JPG = "jpg", "JPG"
        JPEG = "jpeg", "JPEG"

    id = models.BigAutoField(primary_key=True)
    metric = models.CharField(max_length=64, choices=Metric.choices)
    file_format = models.CharField(max_length=16, choices=FileFormat.choices)
    metadata = models.JSONField(blank=True, null=True)
    client_ip = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dashboard_download_events"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["metric", "created_at"]),
        ]

    def __str__(self) -> str:
        created = self.created_at.isoformat() if self.created_at else "unknown"
        return f"{self.get_metric_display()} ({self.file_format}) @ {created}"
