from django.utils import timezone
from pt_backend.models import Case, CaseUploadBatch
from .models import ExpertDataset, ExpertDatasetRow

def build_or_refresh_dataset_from_batch(batch: CaseUploadBatch) -> ExpertDataset:
    """
    Buat/refresh ExpertDataset + rows berdasarkan CaseUploadBatch.
    - data_id    : batch.id
    - file_name  : batch.filename
    - submitted_by: user email/username
    - last_edited: batch.uploaded_at (fallback now)
    """
    submitted_by = (
        getattr(batch.uploaded_by, "email", None)
        or getattr(batch.uploaded_by, "username", None)
        or "unknown"
    )[:150]

    ds, _ = ExpertDataset.objects.update_or_create(
        data_id=str(batch.id),
        defaults={
            "file_name": batch.filename or f"batch_{batch.id}.csv",
            "submitted_by": submitted_by,
            "last_edited": batch.uploaded_at or timezone.now(),
        },
    )

    # rebuild rows idempotent
    ExpertDatasetRow.objects.filter(dataset=ds).delete()
    cases = (
        Case.objects.filter(batch=batch)
        .select_related("disease", "location")
        .order_by("created_at", "id")
    )

    bulk = []
    for idx, c in enumerate(cases, start=1):
        bulk.append(
            ExpertDatasetRow(
                dataset=ds,
                row_number=idx,
                data_id=str(c.id),
                gender=c.gender or "",
                age=c.age,
                city=c.city or getattr(c.location, "city", "") or "",
                status=c.status or "",
                disease_id=str(getattr(c.disease, "id", "") or ""),
                location_id=str(getattr(c, "location_id", "") or ""),
                severity=c.severity or "",
                payload=None,
            )
        )
    if bulk:
        ExpertDatasetRow.objects.bulk_create(bulk)

    return ds
