import os

import django

# Ensure Django knows which settings module to load during pytest runs.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pantau_tular.test_settings")
django.setup()
