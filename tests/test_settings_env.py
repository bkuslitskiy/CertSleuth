"""Settings must tolerate set-but-empty env vars (the GCP .env template left
EMAIL_URL= blank and the first deploy crashed on "Invalid email schema ''")."""
import os
import pathlib
import subprocess
import sys


def test_settings_import_with_empty_email_url():
    repo = pathlib.Path(__file__).resolve().parent.parent
    env = {**os.environ, "EMAIL_URL": "", "DJANGO_SETTINGS_MODULE": "config.settings",
           "DJANGO_SECRET_KEY": "x" * 50, "DATABASE_URL": "sqlite:///:memory:",
           "FIELD_ENCRYPTION_KEY": "QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUE="}
    proc = subprocess.run(
        [sys.executable, "-c",
         "import django; django.setup(); from django.conf import settings; "
         "print(settings.EMAIL_BACKEND)"],
        capture_output=True, text=True, cwd=repo, env=env)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert "console" in proc.stdout          # empty -> console backend, not a crash
