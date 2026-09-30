"""
Settings for ENSA Project Manager (PLAN P4.1).

Everything is configured through environment variables (see .env.example). A local
`.env` file is loaded automatically for development. ENVIRONMENT selects defaults:

- dev  (default): DEBUG on, SQLite, console email, relaxed security.
- prod: DEBUG off, required secrets (the process refuses to start without them),
        HTTPS-only cookies, HSTS, WhiteNoise compressed/manifest static files.
- test: set automatically by `manage.py test`.
"""

import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _load_dotenv(path):
    """Minimal .env loader (no third-party dependency); real env vars win."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).lower() in ("1", "true", "yes", "on")


def env_int(name, default):
    return int(env(name, str(default)))


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


def required(name):
    value = env(name)
    if not value:
        raise ImproperlyConfigured(f"Environment variable {name} is required in production.")
    return value


TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"
ENVIRONMENT = "test" if TESTING else env("ENVIRONMENT", "dev")
if ENVIRONMENT not in ("dev", "test", "prod"):
    raise ImproperlyConfigured("ENVIRONMENT must be dev, test or prod.")
IS_PROD = ENVIRONMENT == "prod"


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", default=not IS_PROD)

if IS_PROD:
    SECRET_KEY = required("DJANGO_SECRET_KEY")
    if SECRET_KEY.startswith("django-insecure") or len(SECRET_KEY) < 50:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a long random value in production.")
    ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS") or required("DJANGO_ALLOWED_HOSTS")
    SITE_URL = required("SITE_URL").rstrip("/")
else:
    # Not a secret: only ever used on developer machines and in tests.
    SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-insecure-key-" + "x" * 40)
    ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver")
    SITE_URL = env("SITE_URL", "http://localhost:8000").rstrip("/")

# Origins trusted for unsafe (POST) requests; defaults to the site itself.
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS") or (
    [SITE_URL] if SITE_URL.startswith("https://") else []
)


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # ENSA Project Manager apps
    "public",
    "accounts",
    "student",
    "teacher",
    "administrator",
    "search",
    # Third party
    "axes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Must stay last: turns failed-login lockouts into responses.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "ensa_project_manager.urls"
WSGI_APPLICATION = "ensa_project_manager.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.badges",
            ],
        },
    },
]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# DATABASE_URL (postgres://user:password@host:5432/name) takes precedence; the older
# DB_ENGINE/DB_* variables are still honoured; SQLite is the development default.


def _database_from_url(url):
    parsed = urlparse(url)
    engines = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "sqlite": "django.db.backends.sqlite3",
    }
    if parsed.scheme not in engines:
        raise ImproperlyConfigured(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")
    if parsed.scheme == "sqlite":
        return {"ENGINE": engines["sqlite"], "NAME": parsed.path or ":memory:"}
    return {
        "ENGINE": engines[parsed.scheme],
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
    }


if env("DATABASE_URL"):
    _db = _database_from_url(env("DATABASE_URL"))
elif env("DB_ENGINE"):
    _db = {
        "ENGINE": env("DB_ENGINE"),
        "NAME": env("DB_NAME", ""),
        "USER": env("DB_USER", ""),
        "PASSWORD": env("DB_PASSWORD", ""),
        "HOST": env("DB_HOST", ""),
        "PORT": env("DB_PORT", ""),
    }
else:
    _db = {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}

if _db["ENGINE"].endswith("postgresql"):
    _db["CONN_MAX_AGE"] = env_int("DB_CONN_MAX_AGE", 60)
    _db["CONN_HEALTH_CHECKS"] = True
DATABASES = {"default": _db}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Nothing relies on a shared cache (badges are uncached, axes uses the DB), so the
# per-process memory cache is enough.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "smart_redirect"
LOGOUT_REDIRECT_URL = "public:homepage"

SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 24 * 7)  # one week
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True  # JS reads the token from the DOM, never from the cookie

# Login throttling (django-axes): N failures for the same username+IP -> lockout.
AXES_FAILURE_LIMIT = env_int("AXES_FAILURE_LIMIT", 5)
AXES_COOLOFF_TIME = timedelta(minutes=env_int("AXES_COOLOFF_MINUTES", 15))
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "registration/lockout.html"
# Behind a reverse proxy (Caddy in production) the client IP is in X-Forwarded-For.
AXES_IPWARE_PROXY_COUNT = env_int("TRUSTED_PROXY_COUNT", 0) or None
if AXES_IPWARE_PROXY_COUNT:
    AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]
# Tests log in with client.login() (no request object); lockout tests re-enable it.
AXES_ENABLED = not TESTING


# ---------------------------------------------------------------------------
# Internationalization — French UI, Moroccan time
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "fr"
TIME_ZONE = env("TIME_ZONE", "Africa/Casablanca")
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(env("STATIC_ROOT", BASE_DIR / "staticfiles"))

MEDIA_URL = "/media/"
MEDIA_ROOT = env("MEDIA_ROOT", str(BASE_DIR / "media"))
# Private files (project deliverables). Never served by the web server: downloads go
# through permission-checked views (student.views.deliverables).
PRIVATE_MEDIA_ROOT = env("PRIVATE_MEDIA_ROOT", str(BASE_DIR / "private"))

if TESTING:
    # The test runner must never write uploads into the working tree.
    _test_files = tempfile.mkdtemp(prefix="ensa-test-files-")
    MEDIA_ROOT = os.path.join(_test_files, "media")
    PRIVATE_MEDIA_ROOT = os.path.join(_test_files, "private")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if IS_PROD
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}

# Upload limits: files above 5 MB go to a temp file; non-file POST bodies are capped.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
    if IS_PROD
    else "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 15)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "ENSA Project Manager <noreply@localhost>")
SERVER_EMAIL = env("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# "Jane Doe <jane@example.com>, ops@example.com" -> error emails in production
ADMINS = [
    (address.split("<")[0].strip() or address, address.split("<")[-1].rstrip(">").strip())
    for address in env_list("ADMINS")
]


# ---------------------------------------------------------------------------
# Logging — everything to stdout (collected by Docker / the process manager)
# ---------------------------------------------------------------------------

LOG_LEVEL = env("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "line": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "line"},
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
            "filters": ["require_debug_false"],
        },
    },
    "filters": {"require_debug_false": {"()": "django.utils.log.RequireDebugFalse"}},
    # Tests exercise error paths on purpose; keep their output readable.
    "root": {"handlers": ["console"], "level": "CRITICAL" if TESTING else LOG_LEVEL},
    "loggers": {
        "django.request": {
            "handlers": ["console", "mail_admins"],
            "level": "CRITICAL" if TESTING else "ERROR",
            "propagate": False,
        },
    },
}


# ---------------------------------------------------------------------------
# Security hardening (automatic whenever DEBUG is off)
# ---------------------------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
    # The reverse proxy (Caddy) terminates TLS and sets X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", default=True)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_HSTS_PRELOAD", default=False)

# HSTS preload is opt-in (DJANGO_HSTS_PRELOAD=True): it is practically irreversible and the
# site may live on a subdomain of a school domain we don't control.
SILENCED_SYSTEM_CHECKS = [] if env_bool("DJANGO_HSTS_PRELOAD", default=False) else ["security.W021"]
