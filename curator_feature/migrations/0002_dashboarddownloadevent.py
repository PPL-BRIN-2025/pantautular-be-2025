from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("curator_feature", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DashboardDownloadEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("metric", models.CharField(choices=[("jumlah_kasus", "Jumlah Kasus"), ("estimasi_prevalensi", "Estimasi Prevalensi"), ("usia", "Usia"), ("jenis_kelamin", "Jenis Kelamin"), ("tingkat_kasus", "Tingkat Kasus"), ("distribusi_sumber_berita", "Distribusi Sumber Berita")], max_length=64)),
                ("file_format", models.CharField(choices=[("png", "PNG"), ("jpg", "JPG"), ("jpeg", "JPEG")], max_length=16)),
                ("metadata", models.JSONField(blank=True, null=True)),
                ("client_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=512)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "dashboard_download_events",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="dashboarddownloadevent",
            index=models.Index(fields=["metric", "created_at"], name="curator_fe_metric_7b5779_idx"),
        ),
    ]
