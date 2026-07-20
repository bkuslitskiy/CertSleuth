"""CertSleuth settings. Security decisions cross-referenced to security.md SEC-###."""
from datetime import timedelta
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DJANGO_DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django_q",
    "axes",  # SEC-021: login brute-force lockout
    "apps.core", "apps.accounts", "apps.catalog", "apps.tracker", "apps.offers", "apps.research",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.RLSSessionMiddleware",  # SEC-008: SET certsleuth.user_id
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.ContentSecurityPolicyMiddleware",  # ASVS V14: strict CSP, no 3rd-party
    "axes.middleware.AxesMiddleware",  # SEC-021: must be last; converts a lockout into a response
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR/'db.sqlite3'}")}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"  # D26: numeric surrogate PKs everywhere
AUTH_USER_MODEL = "accounts.User"

# --- ASVS V2/V3 (SEC-009, security-audit.md) ---
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
]
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
if not DEBUG:  # behind Caddy TLS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# --- SEC-021: login brute-force lockout (django-axes) ---
# AxesStandaloneBackend must precede ModelBackend: it only performs the lockout check and
# defers actual credential verification to ModelBackend.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_HANDLER = "axes.handlers.database.AxesDatabaseHandler"  # shared across gunicorn workers, no Redis
AXES_FAILURE_LIMIT = 5                               # failures before lockout
AXES_COOLOFF_TIME = timedelta(hours=1)              # auto-unlock window
# Lock by source IP (behind Caddy the resolved IP is the real client). IP-based lockout is
# DoS-safe — an attacker can't lock a victim's account, only their own IP — and it also
# catches credential-stuffing that spreads a few guesses across many accounts from one IP.
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
# Django's AuthenticationForm submits the identifier under the field name "username" (even
# though our USERNAME_FIELD is "email"); axes defaults this to USERNAME_FIELD, which would
# read the wrong key and record username=None. Point it at the real form field so the
# targeted account is captured on each AccessAttempt for admin forensics.
AXES_USERNAME_FORM_FIELD = "username"
AXES_RESET_ON_SUCCESS = True                        # a good login clears that IP's failures
AXES_LOCKOUT_TEMPLATE = "registration/lockout.html"
AXES_HTTP_RESPONSE_CODE = 429
if not DEBUG:  # behind Caddy: trust exactly one proxy hop when resolving the client IP
    AXES_IPWARE_PROXY_COUNT = 1

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {"staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}

# EMAIL_URL= (set but empty) must behave like unset — env.email_url's default only
# applies when the var is absent, and an empty string crashes on "invalid schema ''"
# (bit the first GCP deploy, 2026-07-18).
EMAIL_CONFIG = environ.Env.email_url_config(env("EMAIL_URL", default="") or "consolemail://")
vars().update(EMAIL_CONFIG)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="CertSleuth <no-reply@localhost>")

Q_CLUSTER = {  # django-q2: DB broker, fits the e2-micro (no Redis)
    "name": "certsleuth", "workers": 2, "timeout": 300, "retry": 360,
    "orm": "default", "catch_up": False,
}

FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")  # SEC-009
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")

WAITLIST_THRESHOLD = 90  # D1
TIME_ZONE = "UTC"        # per-user TZ stored on User (D27)
USE_TZ = True
