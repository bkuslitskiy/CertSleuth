import os
# config.settings requires DJANGO_SECRET_KEY at import (no default, prod-safe). This is
# the settings module, so its top runs before that import — provide a throwaway here so
# the suite is hermetic (CI sqlite pass and fresh clones have no .env). setdefault keeps
# any real env value.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-insecure-key-not-for-prod")

from config.settings import *  # noqa: E402,F403
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # test speed only
# Manifest storage needs a collectstatic pass; tests render admin templates without one.
STORAGES = {**STORAGES,  # noqa: F405
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
