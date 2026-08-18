"""Minimum Django settings for a SciTeX app. Nothing here is SciTeX-specific
except the two INSTALLED_APPS entries and the template loader finding them.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "not-a-secret-this-is-a-demo"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    # scitex_ui ships the shell template and its static assets.
    "scitex_ui",
    # Your app. Points at the AppConfig, which is what loads manifest.json.
    "hello_world.apps.HelloWorldConfig",
]

MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]

ROOT_URLCONF = "project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # APP_DIRS finds both hello_world/templates/ and scitex_ui's shell.
        "APP_DIRS": True,
        "DIRS": [],
        "OPTIONS": {"context_processors": []},
    }
]

STATIC_URL = "/static/"
USE_TZ = True
