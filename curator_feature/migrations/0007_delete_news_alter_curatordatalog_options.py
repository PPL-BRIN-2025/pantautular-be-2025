from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("curator_feature", "0006_curatordatalog_immutable"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[], 
            state_operations=[
                migrations.DeleteModel(name="News"),
                migrations.AlterModelOptions(
                    name="curatordatalog",
                    options={"default_permissions": ("add", "view"), "ordering": ["-last_edited"]},
                ),
            ],
        ),
    ]
