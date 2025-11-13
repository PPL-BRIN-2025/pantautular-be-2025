from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pt_backend", "0022_backfill_case_batch"),
    ]

    # Intentionally left as a no-op for now to avoid making
    # the foreign key non-null/CASCADE in production.
    operations = []
