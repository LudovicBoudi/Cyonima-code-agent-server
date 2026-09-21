from .base import *  # noqa: F401,F403

DEBUG = True

INSTALLED_APPS += ["django_extensions"]  # noqa: F405

ALLOWED_HOSTS = ["*"]

# Pas de vérification d'email en dev
ACCOUNT_EMAIL_VERIFICATION = "optional"

# EMAIL en console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
