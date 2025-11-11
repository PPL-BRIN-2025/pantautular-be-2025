import os

from .settings import *  # noqa: F401,F403

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
    }
}
PASSWORD_RESET_BASE_URL = "http://testserver/reset"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

SECRET_API_KEYS = [os.getenv("SECRET_API_KEY", "test-api-key")]

CAPTCHA_ENABLED = False
