from django.db import models
from django.utils import timezone

class AdminUserLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=120, db_index=True)
    email = models.EmailField(db_index=True)
    timestamp = models.DateTimeField(db_index=True, default=timezone.now)
    action = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    detail = models.CharField(max_length=120, db_index=True)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_user_logs"
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
            models.Index(fields=["detail"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        return f"{self.username} - {self.action or self.detail}"
