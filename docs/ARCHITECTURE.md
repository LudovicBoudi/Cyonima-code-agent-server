# Architecture — Cyonima Code Agent Server

Portail web **multiuser** d'agent IA de code, portage serveur du concept de
[Cyonima-ia-code-agent](https://github.com/LudovicBoudi/Cyonima-code-agent)
(app desktop locale). L'agent autonome (lecture/écriture/exécution dans un
workspace), le gateway de permissions et le streaming vers Ollama sont
conservés ; ce qui change, c'est la tenance, l'authentification et l'isolation
d'exécution.

## Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend React (SPA, thème violet repris de l'app desktop)    │
│  ├─ Login / inscription (JWT)                                  │
│  ├─ Sidebar : orgs → workspaces → sessions                     │
│  ├─ SessionView (3 colonnes) : chat / raisonnement / fichiers   │
│  └─ WebSocket de streaming (token, thinking, tool_call, …)      │
└───────────────────────────┬───────────────────────────────────┘
                            │ HTTP (DRF) + WS (Channels)
┌───────────────────────────┴───────────────────────────────────┐
│  Backend Django (apps/)                                        │
│  ├─ accounts/       User custom + auth JWT + allauth (SSO)      │
│  ├─ organizations/  Organisation / Team / Membership + RBAC     │
│  ├─ workspaces/     Workspace + sandbox Docker + fichiers       │
│  ├─ sessions/       Session + Message + WebSocket consumer      │
│  ├─ ollama/         Client Ollama partagé (list/pull/show/chat) │
│  └─ agents/         Boucle agent + outils + permissions + prompt │
└───────┬──────────────────┬──────────────────┬──────────────────┘
        │                  │                  │
   PostgreSQL          Redis           Ollama (partagé)
   (tenants,          (channels,       (inférence, modèles
    sessions)          celery)          partagés)
                                            │
                                   Docker (sandbox)
                                un conteneur / workspace
```

## Tenance & rôles

- **Organization** : tenant. Un utilisateur appartient à N organisations via
  `Membership` (rôle `owner` / `admin` / `member`).
- **Team** : sous-groupe d'une organisation. Un workspace peut être rattaché à
  une équipe (ou à toute l'organisation).
- **RBAC** : la visibilité est filtrée par `get_queryset` (les orgs/workspaces
  de l'utilisateur) ; les mutations (création/suppression de workspaces,
  gestion des membres) sont réservées aux `owner`/`admin` via
  `apps/organizations/permissions.py`.

## Authentification

- **Local** : `POST /api/auth/login/` → JWT (SimpleJWT). Inscription via
  `POST /api/auth/register/`.
- **SSO OIDC** : django-allauth (`socialaccount` `openid_connect`). Un provider
  est configuré via env (`OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`,
  `OIDC_SERVER_URL`, `OIDC_PROVIDER_ID`, `OIDC_NAME`) → `SOCIALACCOUNT_PROVIDERS`.
  Flux redirect : le frontend affiche les providers (`GET /api/auth/sso/`) et
  redirige vers `login_url` (`/api/auth/accounts/oidc/<provider>/login/`) → IdP
  → callback → allauth établit la session → redirection `LOGIN_REDIRECT_URL`
  (frontend `/auth/callback`) → `GET /api/auth/session-token/` convertit la
  session en JWT.
- **SSO SAML** : `allauth.socialaccount.providers.saml` est actif ; configuration
  via l'admin Django (SocialApp) ou `SOCIALACCOUNT_PROVIDERS["saml"]`.
- **WebSocket** : le JWT est passé en query string (`?token=`), validé par
  `apps/sessions/middleware.py`.

## Exécution (sandbox)

- Un **workspace** = un dépôt de code + un **conteneur Docker jetable**
  (`sandbox/Dockerfile`), monté en bind-mount sur `/workspace`.
- Les **outils fichiers** (`read_file`, `write_file`, `edit_file`, `glob`,
  `grep`) opèrent directement sur le bind-mount hôte (rapide, pas de round-trip
  Docker).
- **`bash`** s'exécute *dans* le conteneur (isolation réseau/processus). Sans
  Docker, la sandbox se dégrade proprement : outils fichiers OK, `bash` en
  erreur.

### Durcissement

Chaque conteneur est lancé (voir `apps/workspaces/sandbox.py`) avec :

| Contrôle | Valeur |
|---|---|
| Utilisateur | non-root `agent` (UID/GID alignés sur l'hôte) |
| Capabilities | `--cap-drop ALL` |
| Privilèges | `--security-opt no-new-privileges` |
| Réseau | coupé par défaut (`workspace.allow_network` pour l'activer) |
| FS racine | lecture seule + tmpfs `/tmp` et `/home/agent` |
| Limites | mémoire (`SANDBOX_MEM_LIMIT`), CPU (`SANDBOX_CPU_LIMIT`), pids (`SANDBOX_PIDS_LIMIT`) |

> **Alignement UID** : le backend et le sandbox doivent tourner avec le même
> UID/GID (`SANDBOX_UID`/`SANDBOX_GID`, défaut `1000`) pour que le bind-mount
> soit accessible en écriture des deux côtés. Le répertoire volume doit être
> possédé par cet UID (`make sandbox-prep`).

## Boucle agent (`apps/agents/loop.py`)

Équivalent de `SessionManager::agent_loop` :

1. Reconstruit le contexte : system prompt (snapshot workspace + `AGENTS.md` +
   consignes) + historique des messages.
2. Stream via `POST /api/chat` Ollama (NDJSON), émet `token` / `thinking` /
   `tool_call` en temps réel.
3. Si le modèle renvoie des tool calls → gateway de permissions
   (`apps/agents/permissions.py`) : `auto` / `ask` / `deny`. `bash` = `ask` par
   défaut. La demande est **persistée** (`PermissionRequest`) et résolue par le
   frontend (WebSocket `permission_response` ou REST `POST …/respond/`) ; la
   boucle attend la résolution en polling (timeout 600 s).
4. Exécute l'outil, renvoie le résultat au LLM, itère (max 32 tours).
5. Persiste les messages en base et émet `done` (toujours, même en erreur).

## Streaming & exécution des agents

- `SessionConsumer` (Channels) : un WebSocket par session
  (`/ws/sessions/<id>/?token=…`). Il rejoint le groupe `session_<id>`.
- La boucle agent (`apps/agents/loop.py`) est **exécutée par Celery**
  (`apps/agents/tasks.py`, file dédiée `agents`), indépendamment du worker
  web/WS. Les événements sont diffusés via le groupe Channels, donc la
  génération continue et les demandes d'approbation restent consultables après
  une reconnexion.
- **Reprise après crash** : `acks_late` + `reject_on_worker_lost` → si le worker
  meurt en cours de génération, le message est redélivré. La reprise est
  idempotente : message utilisateur créé une seule fois (`run_id`), et la boucle
  tronque les messages partiels du run interrompu (`_prepare`).
- **Orchestration Redis** (`apps/agents/orchestrator.py`) : verrou à valeur
  `agent:run:<session_id>` (anti double-send, ré-acquis en redélivraison) et
  drapeau `agent:cancel:<session_id>` (annulation cross-worker, pollé ≤ 1×/s).
  Sans broker, retombée sur une exécution asyncio locale (dev mono-process).
- Messages entrants : `send`, `cancel`, `permission_response`.
- Événements sortants : `token`, `thinking`, `tool_call`, `tool_result`,
  `permission_request`, `done`, `error`.

## Modèle de données

| Modèle | Rôle |
|---|---|
| `accounts.User` | email = identifiant, `AbstractUser` |
| `organizations.Organization` / `Membership` / `Team` / `TeamMembership` | tenance + rôles |
| `workspaces.Workspace` | dépôt + statut + conteneur |
| `sessions.Session` / `Message` | conversation d'agent (persistance) |
| `agents.PermissionRequest` | demande d'approbation persistée |

## Configuration

- `config/settings/base.py` : commun ; `dev.py` / `prod.py` : environnements.
- Env (`.env`) : `OLLAMA_BASE_URL`, `SANDBOX_IMAGE`, `SANDBOX_VOLUME_ROOT`,
  `POSTGRES_*`, `REDIS_URL`, `USE_SQLITE`, `USE_IN_MEMORY_CHANNEL`, etc.

## Points d'attention / limites actuelles

- **Pull Ollama** : asynchrone via Celery + Redis (`apps/ollama/tasks.py`),
  progression exposée par `GET /api/ollama/pulls/<task_id>/` (polling frontend).
  Un worker `celery -A config worker` est requis ; sans broker, l'API retombe
  sur un pull synchrone (dev uniquement).
- **Provisioning des workspaces** : asynchrone via Celery
  (`apps/workspaces/tasks.py`) — création → `creating`, puis `ready`/`error`
  (polling frontend). La suppression (conteneur + fichiers) est également
  déportée (`destroy_workspace_task`). Sans broker, retombée synchrone.
- **Approbations persistantes** : `PermissionRequest` en base, résolues via REST
  ou WebSocket ; la boucle agent attend en polling (timeout 600 s).
- **Exécution des agents** : déléguée à Celery (file `agents`), avec reprise
  après crash (`acks_late`). Limite : la reprise **rejoue** le run depuis le
  message utilisateur (pas de reprise au token près), ce qui est acceptable pour
  un agent. Nécessite un worker dédié `celery -A config worker -Q agents`.
- Le **SSO OIDC** est vérifié jusqu'à la redirection vers l'IdP ; le callback
  (échange de code, userinfo) dépend d'un IdP réel et reste à valider en
  conditions réelles (Entra ID / Okta / Keycloak).
