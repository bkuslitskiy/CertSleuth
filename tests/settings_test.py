import os
# config.settings requires DJANGO_SECRET_KEY at import (no default, prod-safe). This is
# the settings module, so its top runs before that import — provide a throwaway here so
# the suite is hermetic (CI sqlite pass and fresh clones have no .env). setdefault keeps
# any real env value.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-insecure-key-not-for-prod")

from config.settings import *  # noqa: E402,F403
# Fast in-memory sqlite by default; honor DATABASE_URL when set so the Postgres-only RLS
# suite (SEC-008) can actually run (locally via a throwaway PG, and in the CI postgres job).
if not os.environ.get("DATABASE_URL"):
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # test speed only
# SEC-021: config.settings sets AXES_IPWARE_PROXY_COUNT=1 when DEBUG is off (CI runs with
# DEBUG=False). The test client sends no X-Forwarded-For, so resolve the client IP straight
# from REMOTE_ADDR here — makes the lockout test deterministic in both local and CI runs.
AXES_IPWARE_PROXY_COUNT = None
# Manifest storage needs a collectstatic pass; tests render admin templates without one.
STORAGES = {**STORAGES,  # noqa: F405
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
