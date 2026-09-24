# Cyonima Code Agent — Server (WebApp entreprise)

![Cyonima Code Agent](image.png)

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
- **Auth** : django-allauth (OIDC/SAML/LDAP) + SimpleJWT
- **Inférence** : Ollama (HTTP partagé)
- **Sandbox** : Docker, un conteneur par workspace
- **Frontend** : React + Vite + TypeScript (UI violette reprise de l'app desktop)
- **Base de données** : PostgreSQL

> Guide d'installation complet et configuré : **[`docs/INSTALL.md`](docs/INSTALL.md)**
> (dev SQLite sans Docker, dev Docker, production, HTTPS/LDAP via l'admin,
> dépannage).

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
    system/         Paramètres serveur (HTTPS, LDAP) configurables via l'admin
frontend/           SPA React (voir frontend/README.md)
sandbox/            Image Docker du sandbox d'exécution
docs/               Architecture et installation
```

## Fonctionnalités

- **Sessions d'agent en 3 colonnes** (chat / raisonnement / fichiers) avec
  auto-scroll : le défilement suit le bas tant que l'on n'a pas remonté pour
  lire, dans chacune des colonnes.
- **Catalogue de modèles** (page « Modèles Ollama ») : même sélection par défaut
  que l'app desktop, filtrable, avec statut installé et bouton
  d'installation (`ollama pull`).
- **Modèles à raisonnement** : relance automatique sans *thinking* si un tour ne
  produit que du raisonnement interne, message clair si la réponse reste vide.
- **Permissions par chemin** : lecture/écriture dans le workspace auto-approuvée,
  accès hors roots (ex. `/tmp`) soumis à approbation, `bash` systématiquement
  contrôlé.
- **Bouton arrêter** la génération en cours.
- **Administration (staff)** : gestion des utilisateurs **et paramètres
  serveur** — activation d'**HTTPS** (redirection HTTP→HTTPS, HSTS, cookies
  `Secure`, génération d'un certificat auto-signé + template nginx) et
  authentification **LDAP / Active Directory** (test de connexion intégré,
  compte local créé automatiquement, mot de passe jamais stocké).

## Installation (dev en 5 minutes)

> Procédure complète (prérequis, `.env`, sandbox, HTTPS, LDAP, production,
> dépannage) : **[`docs/INSTALL.md`](docs/INSTALL.md)**.

### Prérequis

Python 3.12+, Node 18+, npm 9+, Docker (Compose v2), et un **Ollama** partagé
(optionnel pour découvrir l'app).

### 1. Configuration

```bash
cp .env.example .env
# Dev rapide sans Postgres/Redis :
#   USE_SQLITE=true
#   USE_IN_MEMORY_CHANNEL=true
```

### 2. Services partagés (optionnel — sautable avec SQLite/mémoire)

```bash
docker compose up -d db redis ollama    # ou : make up
```

### 3. Backend

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
python manage.py migrate
python manage.py createsuperuser        # compte admin (gestion des utilisateurs)
daphne -b 0.0.0.0 -p 8080 config.asgi:application   # API + WS sur :8080
```

### 4. Frontend

```bash
cd frontend && npm install
BACKEND_URL=http://localhost:8080 npm run dev    # SPA sur :5173
```

> `BACKEND_URL` pointe le backend proxifié par Vite (défaut `:8000` ; ici
> daphne sur `:8080`).

### 5. Ollama (optionnel)

```bash
docker run -d -p 11434:11434 ollama/ollama:latest
```

L'application se visite sur **http://localhost:5173/** (Vite proxifie `/api`,
`/ws` et `/admin` vers le backend). Le port **8080** expose uniquement l'API —
un `Page not found` sur `:8080/` est **normal**, la SPA se sert sur `:5173`.

Recommandé ensuite : construire le sandbox d'exécution
(`make sandbox-build && make sandbox-prep`) pour débloquer les commandes
`bash` de l'agent.

### Workers Celery

`pull` de modèles et exécution des agents peuvent tourner dans des workers :

```bash
cd backend && celery -A config worker -l info          # tâches courtes
cd backend && celery -A config worker -Q agents -l info # exécution des agents
```

Sans worker (broker indisponible), le backend retombe sur une exécution
synchrone — pratique en dev.

## API (aperçu)

- `POST /api/auth/login/` → JWT (email + mot de passe) ; accès valable **12 h**,
  auto-renouvelé par le frontend via `POST /api/auth/refresh/` (refus de 401,
  refresh 7 jours).
- `GET  /api/auth/me/` → utilisateur courant
- `GET  /api/orgs/` → organisations de l'utilisateur
- `GET/POST /api/orgs/{org}/workspaces/` → workspaces
- `GET/POST /api/sessions/` → sessions d'agent
- `WS   /ws/sessions/{id}/?token=<jwt>` → streaming agent
- `GET  /api/ollama/models/` → modèles Ollama installés
- `GET  /api/ollama/catalog/` → **catalogue** de modèles recommandés (même
  sélection que l'app desktop : qwen3, ornith-1.5, gemma4, granite4.2…), avec
  statut *installé* et pull direct via `POST /api/ollama/models/{tag}/pull/`
- `GET/PATCH /api/system/config/` → **paramètres serveur** (staff) : HTTPS et
  LDAP ; actions `POST /api/system/config/generate-cert/` (certificat
  auto-signé) et `POST /api/system/config/test-ldap/` (test de connexion)

## Déploiement multi-workers

L'état d'exécution des agents (verrou + annulation) est partagé via **Redis**
(`apps/agents/orchestrator.py`), donc plusieurs processus ASGI peuvent coopérer.
Pour scaler :

```bash
# Redis (obligatoire, pas de USE_IN_MEMORY_CHANNEL)
USE_IN_MEMORY_CHANNEL=false

# N processus ASGI (daphne) derrière un load-balancer
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

> En dev mono-process, on peut garder `USE_IN_MEMORY_CHANNEL=true` et
> `USE_SQLITE=true` (retombée automatique sans Redis).

## Tests

Suite pytest (avec `pytest-django`), utilisant SQLite + channel layer mémoire +
Celery eager (aucun service externe requis) :

```bash
cd backend && pytest          # ou : make test
```

La suite couvre l'auth, les organisations/RBAC, les workspaces, les sessions,
la boucle agent (tool calls, reprise, approbations), l'orchestration Redis
(via `fakeredis`), les tâches Celery et le client Ollama (mock HTTP).

## Release & déploiement

Un tag `v*` déclenche le workflow de release (`.github/workflows/release.yml`)
qui construit et publie trois images sur **GitHub Container Registry**
(`ghcr.io/<owner>/<repo>/<image>`), versionnées (`v1.2.3`, `1.2`, `latest`) :

- **`backend`** — Django + daphne (API REST + WebSocket), statiques via whitenoise ;
- **`frontend`** — nginx servant la SPA et proxy `/api` + `/ws` vers `backend` ;
- **`sandbox`** — image d'exécution jetable (un conteneur par workspace).

Référence de déploiement (remplacer `<image>` par vos images) :

```yaml
services:
  db:         { image: postgres:16-alpine }
  redis:      { image: redis:7-alpine }
  ollama:     { image: ollama/ollama:latest }
  backend:
    image: ghcr.io/<owner>/<repo>/backend:latest
    env_file: .env
    volumes: ["/var/run/docker.sock:/var/run/docker.sock", "./sandbox/workspaces:/sandbox/workspaces"]
  worker:
    image: ghcr.io/<owner>/<repo>/backend:latest
    command: celery -A config worker -l info
  agent-worker:
    image: ghcr.io/<owner>/<repo>/backend:latest
    command: celery -A config worker -Q agents -l info
  frontend:
    image: ghcr.io/<owner>/<repo>/frontend:latest
    ports: ["80:80"]
```

## Licence

MIT — voir [`LICENSE`](LICENSE).
