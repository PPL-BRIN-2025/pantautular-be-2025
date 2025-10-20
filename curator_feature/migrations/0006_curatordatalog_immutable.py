# curator_feature/migrations/0006_curatordatalog_immutable.py
from django.db import migrations

POSTGRESQL_SQL = """
CREATE OR REPLACE FUNCTION curator_feature_datalog_block_mod_del()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'curator_feature_datalog is immutable';
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS curator_feature_datalog_block_update ON curator_feature_datalog;
DROP TRIGGER IF EXISTS curator_feature_datalog_block_delete ON curator_feature_datalog;

CREATE TRIGGER curator_feature_datalog_block_update
BEFORE UPDATE ON curator_feature_datalog
FOR EACH ROW EXECUTE FUNCTION curator_feature_datalog_block_mod_del();

CREATE TRIGGER curator_feature_datalog_block_delete
BEFORE DELETE ON curator_feature_datalog
FOR EACH ROW EXECUTE FUNCTION curator_feature_datalog_block_mod_del();
"""

# SQLite (and other DBs) – use generic triggers
SQLITE_SQL = """
CREATE TRIGGER IF NOT EXISTS curator_feature_datalog_block_update
BEFORE UPDATE ON curator_feature_datalog
BEGIN
  SELECT RAISE(FAIL, 'curator_feature_datalog is immutable');
END;

CREATE TRIGGER IF NOT EXISTS curator_feature_datalog_block_delete
BEFORE DELETE ON curator_feature_datalog
BEGIN
  SELECT RAISE(FAIL, 'curator_feature_datalog is immutable');
END;
"""

def forwards(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(POSTGRESQL_SQL)
    else:
        schema_editor.execute(SQLITE_SQL)

def backwards(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS curator_feature_datalog_block_update ON curator_feature_datalog;
            DROP TRIGGER IF EXISTS curator_feature_datalog_block_delete ON curator_feature_datalog;
            DROP FUNCTION IF EXISTS curator_feature_datalog_block_mod_del();
        """)
    else:
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS curator_feature_datalog_block_update;
            DROP TRIGGER IF EXISTS curator_feature_datalog_block_delete;
        """)

class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("curator_feature", "0005_news"),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
