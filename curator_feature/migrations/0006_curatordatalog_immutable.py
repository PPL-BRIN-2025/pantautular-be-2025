# curator_feature/migrations/0006_curatordatalog_immutable.py
from django.db import migrations

POSTGRESQL_SQL = """
CREATE OR REPLACE FUNCTION curator_feature_datalog_block_mod_del()
RETURNS trigger AS $BODY$
BEGIN
  RAISE EXCEPTION 'curator_feature_datalog is immutable';
  RETURN NULL;
END;
$BODY$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS curator_feature_datalog_block_update ON curator_feature_datalog;
DROP TRIGGER IF EXISTS curator_feature_datalog_block_delete ON curator_feature_datalog;

CREATE TRIGGER curator_feature_datalog_block_update
BEFORE UPDATE ON curator_feature_datalog
FOR EACH ROW EXECUTE FUNCTION curator_feature_datalog_block_mod_del();

CREATE TRIGGER curator_feature_datalog_block_delete
BEFORE DELETE ON curator_feature_datalog
FOR EACH ROW EXECUTE FUNCTION curator_feature_datalog_block_mod_del();
"""


def forwards(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "postgresql":
        schema_editor.execute(POSTGRESQL_SQL)
        return

    if vendor == "sqlite":
        # SQLite (our default test DB) cannot express these triggers, so we skip them.
        print("Skipping curator_feature_datalog immutability triggers (SQLite test environment)")
        return

    print(f"Skipping immutable trigger creation (not supported on {vendor})")


def backwards(apps, schema_editor):
    vendor = schema_editor.connection.vendor

    if vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER IF EXISTS curator_feature_datalog_block_update ON curator_feature_datalog;")
        schema_editor.execute("DROP TRIGGER IF EXISTS curator_feature_datalog_block_delete ON curator_feature_datalog;")
        schema_editor.execute("DROP FUNCTION IF EXISTS curator_feature_datalog_block_mod_del();")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("curator_feature", "0005_news"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

