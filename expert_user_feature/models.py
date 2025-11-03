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
