from django.db import models

class ExpertDataset(models.Model):
    """
    Minimal dataset entity to back the Expert Data Management table.
    You can later replace this with an unmanaged model mapping to your real table.
    """
    data_id      = models.CharField(max_length=64, unique=True, db_index=True)
    file_name    = models.CharField(max_length=255)
    last_edited  = models.DateTimeField()
    submitted_by = models.CharField(max_length=64, db_index=True)

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
    gender = models.CharField(max_length=16)
    age = models.IntegerField()
    city = models.CharField(max_length=128)
    status = models.CharField(max_length=64)
    disease_id = models.CharField(max_length=64)
    location_id = models.CharField(max_length=64)
    severity = models.CharField(max_length=64)
    payload = models.JSONField(blank=True, null=True) 
    class Meta:
        db_table = "expert_dataset_row"
        ordering = ["row_number"]
        indexes = [
            models.Index(fields=["dataset", "row_number"]),
            models.Index(fields=["data_id"]),
        ]
