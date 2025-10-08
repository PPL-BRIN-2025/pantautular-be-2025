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
