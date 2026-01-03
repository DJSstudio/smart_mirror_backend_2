import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Django Security
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")
DEBUG = os.getenv("DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# Installed Apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "mirrors",
]

# Middleware
MIDDLEWARE = [
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "utils.cert_middleware.ClientCertMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

WHITENOISE_ALLOW_ALL_ORIGINS = True

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


ROOT_URLCONF = "config.urls"

# Templates (Admin requires this)
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database (SQLite for now)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db" / "smart_mirror.db",
    }
}

# Static & Media
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = os.getenv("MEDIA_ROOT", BASE_DIR / "media")

# DRF
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ]
}

# Session Transfer Token Config
TRANSFER_TOKEN = {
    "PRIVATE_KEY_PATH": os.getenv("TRANSFER_PRIVATE_KEY_PATH", str(BASE_DIR / "keys/private.pem")),
    "PUBLIC_KEY_PATH": os.getenv("TRANSFER_PUBLIC_KEY_PATH", str(BASE_DIR / "keys/public.pem")),
    "ALGORITHM": os.getenv("TRANSFER_ALG", "RS256"),
    "EXP_SECONDS": int(os.getenv("TRANSFER_EXP", "120")),
}

# Local mirror identity
HOSTNAME = os.getenv("HOSTNAME", "local-mirror")

# Logging Level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DEVICE_IP = os.getenv("DEVICE_IP", "192.168.1.8:8000")
