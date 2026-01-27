#!/bin/bash

set -e

echo "Database configuration (sanitized):"
python - <<'PY'
import os
from urllib.parse import urlparse, unquote

url = os.getenv("DATABASE_URL", "")
if not url:
    print("  DATABASE_URL: not set")
    raise SystemExit(0)

parsed = urlparse(url)
host = parsed.hostname or ""
user = unquote(parsed.username or "")
port = parsed.port or ""

print(f"  host: {host}")
print(f"  user: {user}")
print(f"  port: {port}")

if "pooler.supabase.com" in host and "." not in user:
    print("  WARNING: Supabase pooler requires a tenant-aware username.")
    ref = (
        os.getenv("SUPABASE_PROJECT_REF")
        or os.getenv("SUPABASE_REF")
        or os.getenv("SUPABASE_PROJECT_ID")
        or os.getenv("SUPABASE_DB_PROJECT_REF")
    )
    supabase_url = (
        os.getenv("SUPABASE_URL")
        or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        or os.getenv("SUPABASE_API_URL")
    )
    if ref:
        print("  project_ref: present in env")
    elif supabase_url:
        try:
            supabase_host = urlparse(supabase_url).hostname or supabase_url
            if supabase_host.endswith(".supabase.co"):
                derived_ref = supabase_host.split(".", 1)[0]
                print(f"  derived_project_ref: {derived_ref}")
            else:
                print("  derived_project_ref: unavailable")
        except Exception:
            print("  derived_project_ref: unavailable")
    else:
        print("  project_ref: missing in env")
PY

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting application..."
exec "$@"
