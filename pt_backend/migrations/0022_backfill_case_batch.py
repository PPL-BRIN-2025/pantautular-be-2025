from django.db import migrations
from django.utils import timezone


def backfill_batches(apps, schema_editor):
    Case = apps.get_model("pt_backend", "Case")
    CaseUploadBatch = apps.get_model("pt_backend", "CaseUploadBatch")
    User = apps.get_model("pt_backend", "User")

    qs = Case.objects.filter(batch__isnull=True)
    if not qs.exists():
        return

    now = timezone.now()

    # Build a simple map per uploader. Includes None as a key for cases with no owner.
    user_ids = list(qs.values_list("created_by_id", flat=True).distinct())
    # Fallback user for cases with created_by = NULL
    fallback_user = User.objects.order_by("id").first()
    batch_by_user = {}
    for uid in user_ids:
        uploader_id = uid if uid is not None else (fallback_user.id if fallback_user else None)
        if uploader_id is None:
            # No users exist; cannot create a valid batch row due to FK. Skip.
            continue
        batch = CaseUploadBatch.objects.create(
            uploaded_by_id=uploader_id,
            filename="legacy_import.csv",
            uploaded_at=now,
        )
        batch_by_user[uid] = batch

    # Update in groups per user for efficiency and clarity.
    for uid, batch in batch_by_user.items():
        Case.objects.filter(created_by_id=uid, batch__isnull=True).update(batch_id=batch.id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("pt_backend", "0021_case_created_at"),
    ]

    operations = [
        migrations.RunPython(backfill_batches, reverse_code=noop),
    ]
