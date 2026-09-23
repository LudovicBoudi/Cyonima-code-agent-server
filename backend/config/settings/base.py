"""Django settings de base — communes à tous les environnements."""
import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_SECRET_KEY=(str, "insecure-dev-key"),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    SITE_URL=(str, "http://localhost:8000"),
    FRONTEND_URL=(str, "http://localhost:5173"),
    POSTGRES_DB=(str, "cyonima"),
    POSTGRES_USER=(str, "cyonima"),
    POSTGRES_PASSWORD=(str, "cyonima"),
    POSTGRES_HOST=(str, "localhost"),
    POSTGRES_PORT=(int, 5432),
    REDIS_URL=(str, "redis://localhost:6379/0"),
    OLLAMA_BASE_URL=(str, "http://localhost:11434"),
    OLLAMA_DEFAULT_MODEL=(str, "qwen2.5-coder:7b"),
    SANDBOX_IMAGE=(str, "cyonima/sandbox:latest"),
    SANDBOX_VOLUME_ROOT=(str, str(BASE_DIR.parent / "sandbox" / "workspaces")),
    SANDBOX_UID=(int, 1000),
    SANDBOX_GID=(int, 1000),
    SANDBOX_CAP_DROP=(list, ["ALL"]),
    SANDBOX_MEM_LIMIT=(str, "2g"),
    SANDBOX_CPU_LIMIT=(float, 1.0),
    SANDBOX_PIDS_LIMIT=(int, 512),
    SANDBOX_READ_ONLY=(bool, True),
    SANDBOX_TMPFS_SIZE=(str, "1g"),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
    USE_SQLITE=(bool, False),
    USE_IN_MEMORY_CHANNEL=(bool, False),
    WORKSPACE_LOCAL_ROOTS=(list, [str(Path.home())]),
    WORKSPACE_EXTERNAL_ROOTS=(list, ["/tmp"]),
)

environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

SITE_URL = env("SITE_URL")
FRONTEND_URL = env("FRONTEND_URL")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "allauth.socialaccount.providers.saml",
    "django_filters",
    "channels",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.organizations",
    "apps.workspaces",
    "apps.sessions",
    "apps.ollama",
    "apps.agents",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------
if env("USE_SQLITE"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
            "HOST": env("POSTGRES_HOST"),
            "PORT": env("POSTGRES_PORT"),
        }
    }

# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# django-allauth
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1

ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]

# ---------------------------------------------------------------------------
# SSO (OIDC / SAML) via django-allauth
#
# Flux : le frontend redirige vers `/api/auth/accounts/<provider>/login/` →
# IdP → callback → allauth établit la session → redirection vers
# `LOGIN_REDIRECT_URL` (frontend) → le frontend appelle
# `/api/auth/session-token/` pour convertir la session en JWT.
# ---------------------------------------------------------------------------
LOGIN_REDIRECT_URL = f"{FRONTEND_URL}/auth/callback"
ACCOUNT_LOGOUT_REDIRECT_URL = f"{FRONTEND_URL}/login"

SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_STORE_TOKENS = True

_oidc_apps = []
if env("OIDC_CLIENT_ID", default=""):
    _oidc_apps.append(
        {
            "provider_id": env("OIDC_PROVIDER_ID", default="oidc"),
            "name": env("OIDC_NAME", default="SSO"),
            "client_id": env("OIDC_CLIENT_ID", default=""),
            "secret": env("OIDC_CLIENT_SECRET", default=""),
            "settings": {"server_url": env("OIDC_SERVER_URL", default="")},
        }
    )

SOCIALACCOUNT_PROVIDERS = {
    "openid_connect": {"APPS": _oidc_apps},
    # SAML et autres providers : configurés via l'admin Django (SocialApp) ou
    # en complétant ce dictionnaire (voir docs/ARCHITECTURE.md).
}

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ---------------------------------------------------------------------------
# Channels (WebSocket streaming)
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL")

if env("USE_IN_MEMORY_CHANNEL"):
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("REDIS_URL")
CELERY_RESULT_BACKEND = env("REDIS_URL")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TASK_ROUTES = {
    # Les agents (longs) tournent sur une file dédiée, pour ne pas bloquer
    # les tâches courtes (pull, provisioning).
    "apps.agents.tasks.run_agent_task": {"queue": "agents"},
}

# ---------------------------------------------------------------------------
# Ollama (serveur partagé)
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL")
OLLAMA_DEFAULT_MODEL = env("OLLAMA_DEFAULT_MODEL")

# ---------------------------------------------------------------------------
# Sandbox Docker
# ---------------------------------------------------------------------------
SANDBOX_IMAGE = env("SANDBOX_IMAGE")
SANDBOX_VOLUME_ROOT = env("SANDBOX_VOLUME_ROOT")
SANDBOX_UID = env("SANDBOX_UID")
SANDBOX_GID = env("SANDBOX_GID")
SANDBOX_CAP_DROP = env("SANDBOX_CAP_DROP")
SANDBOX_MEM_LIMIT = env("SANDBOX_MEM_LIMIT")
SANDBOX_CPU_LIMIT = env("SANDBOX_CPU_LIMIT")
SANDBOX_PIDS_LIMIT = env("SANDBOX_PIDS_LIMIT")
SANDBOX_READ_ONLY = env("SANDBOX_READ_ONLY")
SANDBOX_TMPFS_SIZE = env("SANDBOX_TMPFS_SIZE")

# Racines autorisées pour le choix d'un dossier de travail local
# (navigation des répertoires côté serveur). Vide pour désactiver.
WORKSPACE_LOCAL_ROOTS = [
    os.path.realpath(os.path.expanduser(root))
    for root in env("WORKSPACE_LOCAL_ROOTS")
    if root.strip()
]

# Racines externes au workspace où l'agent peut lire/écrire (ex. `/tmp`) —
# toujours APRÈS approbation utilisateur. Défaut: `/tmp` seulement.
WORKSPACE_EXTERNAL_ROOTS = [
    os.path.realpath(os.path.expanduser(root))
    for root in env("WORKSPACE_EXTERNAL_ROOTS")
    if root.strip()
] or ["/tmp"]

# ---------------------------------------------------------------------------
# Internationalisation / fuseaux
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Statiques & médias
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# CSRF : le frontend (Vite) proxifie l'admin Django ; il faut donc approuver
# son origine pour que les formulaires de l'admin (POST) passent le check.
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(["http://localhost:5173", FRONTEND_URL]))

# drf-spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "Cyonima Code Agent Server API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
