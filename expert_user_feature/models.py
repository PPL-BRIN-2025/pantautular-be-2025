from django.db import models


class ExpertDataset(models.Model):
    data_id      = models.CharField(max_length=64, unique=True, db_index=True)
    file_name    = models.CharField(max_length=255)
    last_edited  = models.DateTimeField()
    submitted_by = models.CharField(max_length=150, db_index=True)

    class Meta:
        db_table = "expert_dataset"
        ordering = ["-last_edited"]

    def __str__(self) -> str:
        return f"{self.data_id} • {self.file_name}"


class ExpertDatasetRow(models.Model):
    dataset = models.ForeignKey(
        ExpertDataset,
        on_delete=models.CASCADE,
        related_name="rows",
    )
    row_number = models.PositiveIntegerField()
    data_id = models.CharField(max_length=64)
    gender = models.CharField(max_length=16, blank=True, default="")
    age = models.IntegerField(null=True, blank=True)
    city = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(max_length=64, blank=True, default="")
    disease_id = models.CharField(max_length=64, blank=True, default="")
    location_id = models.CharField(max_length=64, blank=True, default="")
    severity = models.CharField(max_length=64, blank=True, default="")
    payload = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = "expert_dataset_row"
        ordering = ["row_number"]
        indexes = [
            models.Index(fields=["dataset", "row_number"]),
            models.Index(fields=["data_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.dataset_id}#{self.row_number}"


class ExpertDataLog(models.Model):
    """
    Immutable audit log untuk aksi expert (upload/import/delete/update).
    Mirip curator_feature_datalog tapi namespace expert.
    """
    id = models.BigAutoField(primary_key=True)
    data_id = models.UUIDField()                          # batch.id atau case.id
    title = models.CharField(max_length=255)              # "upload csv", "delete batch", "create case", "update case"
    last_edited = models.DateTimeField(auto_now_add=True)
    submitted_by = models.CharField(max_length=150)       # username/email
    note = models.TextField(blank=True, default="")    # filename, counts, dsb

    class Meta:
        db_table = "expert_feature_datalog"
        ordering = ["-last_edited"]
        indexes = [
            models.Index(fields=["data_id"]),
            models.Index(fields=["submitted_by"]),
            models.Index(fields=["-last_edited"]),
        ]
        default_permissions = ("add", "view")  # tidak expose change/delete

    def __str__(self) -> str:
        return f"{self.data_id} - {self.title} by {self.submitted_by}"

    # immutable guard
    def save(self, *args, **kwargs):
        if self.pk and ExpertDataLog.objects.filter(pk=self.pk).exists():
            raise ValueError("ExpertDataLog entries are immutable and cannot be modified.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("ExpertDataLog entries are immutable and cannot be deleted.")
