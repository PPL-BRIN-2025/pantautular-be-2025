from django.db import migrations

SQL = """
-- add columns if they don't exist
ALTER TABLE public.admin_feature_userlog
  ADD COLUMN IF NOT EXISTS "timestamp" timestamptz NULL,
  ADD COLUMN IF NOT EXISTS "note" text NULL;

-- backfill timestamp from created_at if still null
UPDATE public.admin_feature_userlog
SET "timestamp" = COALESCE("timestamp", created_at);

-- enforce NOT NULL
ALTER TABLE public.admin_feature_userlog
  ALTER COLUMN "timestamp" SET NOT NULL;

-- index for timestamp (idempotent)
CREATE INDEX IF NOT EXISTS admin_feature_userlog_timestamp_idx
  ON public.admin_feature_userlog("timestamp");
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("admin_feature", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
