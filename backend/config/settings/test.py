"""Settings de test : SQLite fichier, channel layer mémoire, Celery eager, sans Docker."""
from .base import *  # noqa: F401,F403

DEBUG = False

SECRET_KEY = "test-secret-key-not-for-production-0123456789"

# SQLite fichier (partagé entre threads de sync_to_async)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",  # noqa: F405
        "TEST": {"NAME": BASE_DIR / "test_db.sqlite3"},  # noqa: F405
    }
}

CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False

# Sandbox : pas de Docker en test (les tests mockent si besoin)
SANDBOX_VOLUME_ROOT = BASE_DIR.parent / "sandbox" / "test_workspaces"  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
