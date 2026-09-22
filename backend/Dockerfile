FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Statiques (admin/API) servies par whitenoise
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# ASGI (HTTP + WebSocket Channels)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
