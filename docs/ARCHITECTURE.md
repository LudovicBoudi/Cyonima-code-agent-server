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
- **SSO** : django-allauth (`socialaccount` OIDC + SAML). Le login social
  utilise le flux redirect classique (`/api/auth/accounts/<provider>/login/`),
  puis `GET /api/auth/session-token/` convertit la session en JWT pour l'API.
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

## Boucle agent (`apps/agents/loop.py`)

Équivalent de `SessionManager::agent_loop` :

1. Reconstruit le contexte : system prompt (snapshot workspace + `AGENTS.md` +
   consignes) + historique des messages.
2. Stream via `POST /api/chat` Ollama (NDJSON), émet `token` / `thinking` /
   `tool_call` en temps réel.
3. Si le modèle renvoie des tool calls → gateway de permissions
   (`apps/agents/permissions.py`) : `auto` / `ask` / `deny`. `bash` = `ask` par
   défaut (le frontend affiche un dialogue d'approbation, la réponse transite
   par le WebSocket `permission_response`).
4. Exécute l'outil, renvoie le résultat au LLM, itère (max 32 tours).
5. Persiste les messages en base et émet `done` (toujours, même en erreur).

## Streaming

- `SessionConsumer` (Channels) : un WebSocket par session
  (`/ws/sessions/<id>/?token=…`).
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

## Configuration

- `config/settings/base.py` : commun ; `dev.py` / `prod.py` : environnements.
- Env (`.env`) : `OLLAMA_BASE_URL`, `SANDBOX_IMAGE`, `SANDBOX_VOLUME_ROOT`,
  `POSTGRES_*`, `REDIS_URL`, `USE_SQLITE`, `USE_IN_MEMORY_CHANNEL`, etc.

## Points d'attention / limites actuelles

- Le **pull Ollama** est synchrone (pas de progression streamée) — à faire via
  Celery + Redis.
- Le **provisioning** des workspaces est synchrone (clone git + démarrage
  conteneur) — à déporter en tâche Celery.
- L'**approbation** des commandes est stockée en mémoire par connexion
  WebSocket ; une reconnexion perd les demandes en attente.
- Le **SSO** (OIDC/SAML) est structuré mais pas testé de bout en bout.
- La **sandbox** doit être durcie (utilisateur non-root, `--cap-drop`,
  `--network=none`, limites CPU/mémoire) pour un usage production.
