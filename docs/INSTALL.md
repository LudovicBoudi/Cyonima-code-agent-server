# Installation & configuration — Cyonima Code Agent Server

Ce guide détaille les procédures d'installation, de configuration et de mise
en production de la WebApp. Le serveur comprend :

- **backend** Django 5.2 (API REST + WebSocket via Channels),
- **frontend** React/Vite (SPA, proxifiée par nginx en prod, par Vite en dev),
- **sandbox** Docker d'exécution jetable (un conteneur par workspace),
- services partagés : **PostgreSQL**, **Redis** (channels + Celery) et
  **Ollama** (inférence).

---

## 1. Prérequis

| Composant | Version minimale | Rôle |
|---|---|---|
| Python | 3.12 | backend |
| Node.js | 18+ | frontend |
| npm | 9+ | frontend |
| Docker (avec Compose v2) | 24 | services partagés + sandbox |
| Ollama | récent | inference (optionnel si déjà installé ailleurs) |

L'inférence est fournie par un **Ollama partagé** (machine distante ou
conteneur local). Elle est nécessaire pour utiliser les sessions d'agent.

> **Sans Docker ?** En développement, PostgreSQL/Redis peut être remplacé par
> SQLite + un channel layer en mémoire (`USE_SQLITE=true`,
> `USE_IN_MEMORY_CHANNEL=true`). Le sandbox d'exécution reste Docker-only.

---

## 2. Récupération du code

```bash
git clone <your-repo-url> cyonima-server
cd cyonima-server
```

---

## 3. Configuration d'environnement

Chaque environnement (dev, prod) est piloté par un fichier `.env` lu depuis la
racine du dépôt. Un exemple est fourni :

```bash
cp .env.example .env
```

### Réglages essentiels

```dotenv
# Identité du service
DJANGO_SECRET_KEY=change-me-par-une-longue-chaine-aleatoire
DJANGO_DEBUG=true                        # false en production
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 # host(s) public(s) en prod
DJANGO_SETTINGS_MODULE=config.settings.dev   # ou .prod

# URLs publiques (utilisées pour les callbacks SSO et le CORS)
SITE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173

# Base de données — soit PostgreSQL, soit SQLite (dev rapide)
POSTGRES_DB=cyonima
POSTGRES_USER=cyonima
POSTGRES_PASSWORD=cyonima
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
USE_SQLITE=false     # true = SQLite sur backend/db.sqlite3 (aucun service)

# Redis — channels WebSocket + broker Celery
REDIS_URL=redis://localhost:6379/0
USE_IN_MEMORY_CHANNEL=false  # true = channel layer en mémoire (dev mono-process)

# Ollama partagé
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=qwen2.5-coder:7b

# Racines de navigation pour le choix du dossier de travail local
# WORKSPACE_LOCAL_ROOTS=["/home/cyonima/projets"]

# Sandbox Docker
SANDBOX_IMAGE=cyonima/sandbox:latest
SANDBOX_VOLUME_ROOT=./sandbox/workspaces
SANDBOX_UID=1000   # UID/GID utilisateur non-root du sandbox
SANDBOX_GID=1000
SANDBOX_MEM_LIMIT=2g
SANDBOX_CPU_LIMIT=1.0
SANDBOX_PIDS_LIMIT=512
SANDBOX_READ_ONLY=true
SANDBOX_TMPFS_SIZE=1g

# SSO OIDC (optionnel — laisser OIDC_CLIENT_ID vide pour désactiver)
OIDC_PROVIDER_ID=oidc
OIDC_NAME=SSO
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
OIDC_SERVER_URL=
```

> La liste complète et les valeurs par défaut sont dans
> `backend/config/settings/base.py` (bloc `env = environ.Env(...)`).

---

## 4. Installation en développement

### 4.1 Option A — démarrage rapide (SQLite + mémoire, aucun service)

Convient pour découvrir l'application : aucun conteneur nécessaire.

```dotenv
# .env
USE_SQLITE=true
USE_IN_MEMORY_CHANNEL=true
DJANGO_SETTINGS_MODULE=config.settings.dev
```

### 4.2 Option B — services partagés via Docker

Lance PostgreSQL + Redis + Ollama :

```bash
docker compose up -d db redis ollama
# ou simplement :
make up
```

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt

# Base de données + compte admin initial
cd backend
python manage.py migrate

# (recommandé) un compte d'administration, nécessaire pour gérer les comptes
python manage.py createsuperuser

# API + WebSocket (prochain terminal optionnel : daphne en arrière-plan)
daphne -b 0.0.0.0 -p 8080 config.asgi:application
```

En dev, le backend standard (`python manage.py runserver`) fonctionne aussi,
mais **daphne** est recommandé car il gère les WebSockets du streaming.

### Frontend

```bash
cd frontend
npm install
npm run dev        # SPA servie sur http://localhost:5173
```

**Vite proxifie** `/api`, `/ws` et `/admin` vers le backend. Par défaut il
cible `http://localhost:8000` ; pour pointer vers daphne sur le port 8080 :

```bash
BACKEND_URL=http://localhost:8080 npm run dev
```

### Ollama (si les pulls de modèles sont souhaités)

```bash
docker run -d -p 11434:11434 ollama/ollama:latest
```

### Vérification

1. Ouvrir **http://localhost:5173/** — la page de connexion s'affiche.
2. Se connecter avec le superutilisateur créé à l'étape 4.2.
3. Menu **Modèles Ollama** → installer un modèle (ex. `qwen2.5-coder:7b`).
4. Créer une session : nom + dossier de travail local.

### Workers Celery

En l'absence de Redis (option 4.1), les tâches s'exécutent de façon synchrone.
Avec Redis, deux files sont utilisées :

```bash
cd backend
celery -A config worker -l info          # tâches courtes (pull modèles…)
celery -A config worker -Q agents -l info  # exécution des agents (longue)
```

Le Makefile regroupe ces commandes :

```bash
make up           # db + redis + ollama
make backend      # runserver (backend)
make frontend     # vite dev
make migrate      # python manage.py migrate
make test         # pytest
make superuser    # createsuperuser
```

---

## 5. Sandbox d'exécution

Les agents exécutent leurs commandes **dans des conteneurs Docker jetables**
(un par workspace), construits à partir de `sandbox/` :

```bash
make sandbox-build   # docker build -t cyonima/sandbox:latest
make sandbox-prep    # crée sandbox/workspaces et ajuste l'ownership (UID/GID)
```

Sans cela, l'agent fonctionne en mode « dégradé » : lecture/écriture de
fichiers disponibles, mais exécution `bash` indisponible.

---

## 6. Paramètres serveur depuis l'interface (HTTPS & LDAP)

L'onglet **Administration → Paramètres** (accessible aux comptes *staff*)
pilote la configuration serveur **en base, à chaud** — aucune édition de
fichiers ni redémarrage nécessaire.

### 6.1 HTTPS

1. Renseigner le **domaine** public (ex. `agent.cyonima.dev`).
2. Activer « Activer la politique HTTPS » puis **Enregistrer**.

Effet de l'activation :

- redirection permanente **HTTP → HTTPS** (y compris derrière un proxy, via
  `X-Forwarded-Proto`) ;
- en-tête **`Strict-Transport-Security`** (`max-age=31536000; includeSubDomains`) ;
- attribut **`Secure`** ajouté à tous les cookies émis.

Certificat : un bouton **« Générer auto-signé »** produit un certificat RSA
2048 (valable 825 jours) et écrit dans `backend/data/tls/` :

- `<domaine>.crt` / `<domaine>.key` (PEM),
- `https-site.conf` : site nginx prêt à l'emploi (redirect 80→443,
  proxy `/api`, `/ws`, `/admin` vers le backend, statiques SPA).

La politique HTTPS est **inactive** sur `localhost` en développement pour ne
pas casser l'UI.

> En production derrière un reverse-proxy existant, préférez un certificat
> émis par une autorité (Let's Encrypt) — ces fichiers peuvent être fournis
> par import dans l'UI.

### 6.2 LDAP / Active Directory

1. Activer « Activer l'authentification LDAP ».
2. Renseigner par exemple :

   | Champ | AD | OpenLDAP |
   |---|---|---|
   | URI | `ldap://dc.ad.example.fr:389` | `ldap://ldap.example.fr:389` |
   | Utilisateur de liaison | `CN=svc-agent,OU=Services,DC=ad,DC=example,DC=fr` | `cn=admin,dc=example,dc=fr` |
   | Base DN | `DC=ad,DC=example,DC=fr` | `dc=example,dc=fr` |
   | Attribut de connexion | `sAMAccountName` | `uid` |
   | Filtre (optionnel) | `(&(objectClass=user)(sAMAccountName=%(user)s))` | `(&(objectClass=posixAccount)(uid=%(user)s))` |
   | Domaine d'email de repli | `ad.example.fr` | `example.fr` |

3. **« Tester la connexion »** permet de valider la liaison avant d'enregistrer
   (les valeurs saisies sont appliquées de façon éphémère, sans écriture).

Fonctionnement au login :

1. **bind service** (DN + mot de passe, ou liaison anonyme si vide) ;
2. **recherche** de l'utilisateur (filtre avec remplacement de `%(user)s`) ;
3. **rebind utilisateur** sur son propre DN pour vérifier son mot de passe ;
4. **compte local créé automatiquement** (login par email, nom complet
   renseigné) ; le mot de passe utilisateur **n'est jamais stocké**.

Si un compte local existe avec le même email, il est réutilisé ; un compte
désactivé localement (`is_active=false`) reste bloqué.

---

## 7. Déploiement en production

La construction d'images est automatisée par la CI sur **GitHub Container
Registry** (`ghcr.io/<owner>/<repo>/{backend,frontend,sandbox}`), pour chaque
tag `v*`.

```bash
# 1. Préparer l'environnement
cp .env.example .env
#    → DJANGO_SECRET_KEY (longue), DJANGO_DEBUG=false,
#      DJANGO_ALLOWED_HOSTS=<domaine public>, DJANGO_SETTINGS_MODULE=config.settings.prod,
#      IMAGE_PREFIX=ghcr.io/<owner>/<repo>, IMAGE_TAG=latest

# 2. Préparer le sandbox
make sandbox-build && make sandbox-prep

# 3. Déployer
docker compose -f docker-compose.prod.yml up -d --wait
```

L'application est alors accessible sur **http://<ip-serveur>/** via le nginx du
conteneur `frontend` (ports `80:80`).

### HTTPS en production

Activez HTTPS dans **Administration → Paramètres** (cf. §6.1) sur le domaine
public. Pour une terminaison TLS derrière ce nginx, montez
`backend/data/tls/` dans le conteneur `frontend` et copiez le site généré :

```yaml
  frontend:
    image: ${IMAGE_PREFIX}/frontend:${IMAGE_TAG:-latest}
    ports: ["443:443", "80:80"]
    volumes:
      - ./backend/data/tls:/etc/nginx/tls:ro
```

Puis, dans le conteneur : copier `/etc/nginx/tls/https-site.conf` vers
`/etc/nginx/conf.d/` et `nginx -s reload`.

---

## 8. Tests

Aucun service externe requis (SQLite + channel layer mémoire + Celery eager) :

```bash
cd backend && pytest
# ou : make test
```

Couverture : auth, organisations/RBAC, workspaces, sessions, boucle agent,
orchestration Redis (via `fakeredis`), tâches Celery, client Ollama (mock
HTTP), politique HTTPS et backend LDAP (mocks).

---

## 9. Dépannage

| Symptôme | Cause probable / correctif |
|---|---|
| Le frontend reçoit des erreurs réseau sur `/api` | Vite cible un backend absent : vérifier `BACKEND_URL` (ou port 8000 par défaut) et relancer `npm run dev`. |
| `Page not found` sur `localhost:8080/` | Normal : le port backend expose l'API (DRF), pas la SPA. Visiter `http://localhost:5173/`. |
| Login refusé alors que le compte existe | À la création de session, l'inscription publique est fermée : seuls les *staff* créent des comptes depuis **Administration → Utilisateurs**. |
| `pull` de modèles sans Ollama | Installer ou pointer `OLLAMA_BASE_URL` ; vérifier `curl http://localhost:11434/api/tags`. |
| Léchage d'UID sandbox / permission refusée | Refaire `make sandbox-prep` avec les mêmes `SANDBOX_UID/SANDBOX_GID`. |
| LDAP : « liaison service impossible » | Vérifier le DN de liaison et son mot de passe (serveur, base). Le **« Tester la connexion »** de l'UI précise l'étape en échec. |
| HTTPS : la redirection ne se déclenche pas | La politique est inactive sur `localhost`/hosts locaux en dev — tester depuis le domaine public. |