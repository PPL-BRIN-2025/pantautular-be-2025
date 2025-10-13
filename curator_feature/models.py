from django.db import models

class BackendCase(models.Model):
    id = models.UUIDField(primary_key=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, null=True, blank=True)
    disease_id = models.UUIDField(null=True, blank=True)
    location_id = models.UUIDField(null=True, blank=True)
    severity = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "pt_backend_case"

class CuratorDataLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    data_id = models.UUIDField()             
    title = models.CharField(max_length=255)    
    last_edited = models.DateTimeField(auto_now_add=True)
    submitted_by = models.CharField(max_length=150)
    note = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "curator_feature_datalog"
        indexes = [
            models.Index(fields=["data_id"]),
            models.Index(fields=["submitted_by"]),
            models.Index(fields=["-last_edited"]),
        ]
        ordering = ["-last_edited"]

    def __str__(self):
        return f"{self.data_id} - {self.title} by {self.submitted_by}"
