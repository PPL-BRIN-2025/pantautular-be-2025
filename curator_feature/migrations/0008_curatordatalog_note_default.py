from django.db import migrations, models


def set_null_notes_to_blank(apps, schema_editor):
    CuratorDataLog = apps.get_model("curator_feature", "CuratorDataLog")
    CuratorDataLog.objects.filter(note__isnull=True).update(note="")


class Migration(migrations.Migration):

    dependencies = [
        ("curator_feature", "0007_delete_news_alter_curatordatalog_options"),
    ]

    operations = [
        migrations.RunPython(set_null_notes_to_blank, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="curatordatalog",
            name="note",
            field=models.TextField(blank=True, default=""),
        ),
    ]
