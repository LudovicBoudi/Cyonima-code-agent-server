import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("cyonima")
app.config_from_object("django.conf:settings", namespace="CELERY")

import django  # noqa: E402

django.setup()

app.autodiscover_tasks()
