import os

from .base import *  # noqa: F401,F403

DEBUG = True

INSTALLED_APPS += ["django_extensions"]  # noqa: F405

ALLOWED_HOSTS = ["*"]

# En dev, Redis n'est pas forcément démarré : le canal WS et le broker passent
# par défaut en mémoire. Forcer Redis en dev avec USE_IN_MEMORY_CHANNEL=0.
if os.environ.get("USE_IN_MEMORY_CHANNEL") != "0":
    USE_IN_MEMORY_CHANNEL = True  # noqa: F405
    CHANNEL_LAYERS = {  # noqa: F405
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

# Pas de vérification d'email en dev
ACCOUNT_EMAIL_VERIFICATION = "optional"

# EMAIL en console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
