from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("pt_backend", "0020_caseuploadbatch_case_batch"),
    ]

    operations = [
        migrations.AddField(
            model_name="case",
            name="created_at",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                db_index=True,
                editable=False,
            ),
            preserve_default=False,
        ),
    ]

