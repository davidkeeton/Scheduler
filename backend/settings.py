import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "development-only")
DEBUG = os.environ.get("APP_ENV", "alpha") == "alpha"
ALPHA_AUTO_ADMIN = os.environ.get("ALPHA_AUTO_ADMIN", "0") == "1"
if ALPHA_AUTO_ADMIN and not DEBUG:
    raise RuntimeError("Alpha automatic admin must not be enabled in production")
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "api"]
INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.auth", "core"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "urls"
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": os.environ.get("DB_NAME", "scheduler"), "USER": os.environ.get("DB_USER", "scheduler"), "PASSWORD": os.environ.get("DB_PASSWORD", "local-alpha-only"), "HOST": os.environ.get("DB_HOST", "db"), "PORT": "5432"}}
if os.environ.get("LOCAL_SQLITE_TEST") == "1":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "local-test.sqlite3"}}
USE_TZ = True
TIME_ZONE = "America/Vancouver"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
