from django.core.validators import validate_ipv46_address
from django.db import models

class BackendCase(models.Model):
    id = models.UUIDField(primary_key=True)
    gender = models.CharField(max_length=10, blank=True, default="")
    age = models.IntegerField(null=True, blank=True)
    city = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=20, blank=True, default="")
    disease_id = models.UUIDField(null=True, blank=True)
    location_id = models.UUIDField(null=True, blank=True)
    severity = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        managed = False 
        db_table = "pt_backend_case"


class CuratorDataLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    data_id = models.UUIDField()
    title = models.CharField(max_length=255)
    last_edited = models.DateTimeField(auto_now_add=True)
    submitted_by = models.CharField(max_length=150)
    note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "curator_feature_datalog"
        indexes = [
            models.Index(fields=["data_id"]),
            models.Index(fields=["submitted_by"]),
            models.Index(fields=["-last_edited"]),
        ]
        ordering = ["-last_edited"]
        # optionally: limit Django's default perms so there's no "change"/"delete"
        default_permissions = ("add", "view")

    def __str__(self):
        return f"{self.data_id} - {self.title} by {self.submitted_by}"

    # --- IMMUTABILITY GUARDS (ORM layer) ---
    def save(self, *args, **kwargs):
        if self.pk and CuratorDataLog.objects.filter(pk=self.pk).exists():
            raise ValueError("CuratorDataLog entries are immutable and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("CuratorDataLog entries are immutable and cannot be deleted.")


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
    client_ip = models.CharField(
        max_length=45,
        blank=True,
        default="",
        validators=[validate_ipv46_address],
    )
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
    

class ContributorSubmission(models.Model):
    STATUS_CHOICES = [
        ("WAITING_FOR_APPROVAL", "Waiting for Approval"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("NEED_REVISION", "Need Revision"),
    ]

    id = models.UUIDField(primary_key=True, editable=False)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, default="")
    submitted_by = models.CharField(max_length=150)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="WAITING_FOR_APPROVAL")

    has_unseen_update = models.BooleanField(default=False)
    last_notified_status = models.CharField(max_length=30, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "contributor_submissions"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["submitted_by"]),
            models.Index(fields=["status"]),
            models.Index(fields=["title"]),
        ]

    def save(self, *args, **kwargs):
        # prevent updates to title/content after review
        if self.pk:
            old = ContributorSubmission.objects.filter(pk=self.pk).first()
            if old and old.status != "WAITING_FOR_APPROVAL":
                raise ValueError("Reviewed submissions cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Contributor submissions cannot be deleted (audit requirement).")
