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

class Migration(migrations.Migration):

    dependencies = [
        ("admin_feature", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop),
            ],
            state_operations=[
                # No state changes: 0001 already says these fields exist.
            ],
        ),
    ]
