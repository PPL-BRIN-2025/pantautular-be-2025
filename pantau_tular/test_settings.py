from .settings import (
    BASE_DIR,
    SECRET_KEY,
    DEBUG,
    ALLOWED_HOSTS,
    INSTALLED_APPS,
    MIDDLEWARE,
    ROOT_URLCONF,
    TEMPLATES,
    WSGI_APPLICATION,
    DATABASES,
    AUTH_PASSWORD_VALIDATORS,
    LANGUAGE_CODE,
    TIME_ZONE,
    USE_I18N,
    USE_TZ,
    STATIC_URL
)

# Use in-memory SQLite database for testing
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Disable password hashing to speed up tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable logging during tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
}

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "user": None,
        "password_reset": None,
    },
}

# Disable migrations during tests
class DisableMigrations:
    def __contains__(self, item):
        return True #pragma: no cover

    def __getitem__(self, item):
        return None #pragma: no cover

# Define a simple SECRET_KEY for testing
SECRET_KEY = 'test-secret-key-for-ci'