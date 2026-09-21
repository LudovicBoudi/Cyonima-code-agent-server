# Cyonima Code Agent — Server (WebApp entreprise)

Portail web **multiuser** d'agent IA de code, reprenant le concept de
[Cyonima-ia-code-agent](https://github.com/LudovicBoudi/Cyonima-code-agent)
(agent local mono-utilisateur) pour en faire une plateforme d'entreprise.

## Différences avec l'app desktop

| Aspect | Desktop (Tauri) | Serveur (Django) |
|---|---|---|
| Déploiement | Local, mono-utilisateur | Serveur, multi-tenant |
| Auth | Aucune | SSO (OIDC/SAML/LDAP) + email/mot de passe |
| Exécution | Sur la machine locale | Conteneurs Docker par workspace |
| Inférence | Ollama local | Ollama serveur partagé |
| Données | SQLite local | PostgreSQL |

## Stack

- **Backend** : Django 5.2 + DRF + Channels (WebSocket streaming) + Celery/Redis
- **Auth** : django-allauth (OIDC/SAML) + SimpleJWT
- **Inférence** : Ollama (HTTP partagé)
- **Sandbox** : Docker, un conteneur par workspace
- **Frontend** : React + Vite + TypeScript (UI violette reprise de l'app desktop)
- **Base de données** : PostgreSQL

## Structure

```
backend/            Application Django
  config/           settings (base/dev/prod), urls, asgi/wsgi, celery
  apps/
    accounts/       User custom + auth (JWT, allauth)
    organizations/  Organisations, équipes, membres, RBAC
    workspaces/     Workspaces, conteneurs sandbox, fichiers
    sessions/       Sessions d'agent + messages + WebSocket
    ollama/         Client Ollama (list/pull/delete/show)
    agents/         Boucle agent, outils, permissions, prompt
frontend/           SPA React (voir frontend/README.md)
sandbox/            Image Docker du sandbox d'exécution
```

## Démarrage rapide (dev)

```bash
cp .env.example .env

# 1. Services (Postgres, Redis, Ollama)
make up

# 2. Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# 3. Sandbox (image Docker)
make sandbox-build

# 4. Frontend (dans un autre terminal)
cd frontend && npm install && npm run dev
```

## API (aperçu)

- `POST /api/auth/login/` → JWT (email + mot de passe)
- `GET  /api/auth/me/` → utilisateur courant
- `GET  /api/orgs/` → organisations de l'utilisateur
- `GET/POST /api/orgs/{org}/workspaces/` → workspaces
- `GET/POST /api/sessions/` → sessions d'agent
- `WS   /ws/sessions/{id}/?token=<jwt>` → streaming agent
- `GET  /api/ollama/models/` → modèles Ollama installés

## Licence

MIT — voir [`LICENSE`](LICENSE).
