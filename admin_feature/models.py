from django.db import models
from django.utils import timezone

class AdminUserLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=150, db_index=True)
    email = models.EmailField(db_index=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    action = models.CharField(max_length=100, null=True, blank=True, db_index=True)   
    detail = models.TextField(null=True, blank=True, db_index=True)                 
    note = models.TextField(null=True, blank=True)                                    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_feature_userlog"
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        return f"{self.username} - {self.action or self.detail} @ {self.created_at}"

class PtBackendUser(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, db_index=True)
    email = models.EmailField(max_length=254, db_index=True)
    last_login = models.DateTimeField(null=True, blank=True)
    role = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "pt_backend_user"
        managed = False  

    def __str__(self):
        return f"{self.name} ({self.email})"