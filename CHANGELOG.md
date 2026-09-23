# Changelog

Toutes les évolutions notables de Cyonima Code Agent Server sont consignées ici.
Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le
versionnage [SemVer](https://semver.org/lang/fr/).

## [Unreleased]

### Modifié

- **Création de session à la manière de l'app desktop** : plus d'organisations
  ou workspaces dans l'interface. L'utilisateur se connecte, crée une session en
  donnant un **nom de projet** et en choisissant un **dossier de travail local**
  (navigation serveur bornée par `WORKSPACE_LOCAL_ROOTS`). Une organisation
  personnelle et un workspace sont créés automatiquement en arrière-plan ; le
  workspace pointe sur le dossier sélectionné. L'approche « runner local » a été
  abandonnée (le compagnon `runner/` et les éléments associés ont été retirés).

## [0.1.0] — 2026-09-22

Première version : portage serveur multi-tenant de
[Cyonima-ia-code-agent](https://github.com/LudovicBoudi/Cyonima-code-agent)
(app desktop locale) vers une plateforme web d'entreprise (Python + Django).

### Ajouté

- **Multi-tenancy & RBAC** : organisations, équipes, membres et rôles
  (`owner` / `admin` / `member`), filtrage de visibilité et contrôle des
  mutations.
- **Authentification** : JWT (SimpleJWT) + inscription locale ; **SSO OIDC**
  via django-allauth (config par env : `OIDC_*`), SAML disponible.
- **Workspaces** : dépôts de code avec sandbox Docker jetable (un conteneur par
  workspace), clone git, fichiers (read/write/edit/glob/grep) et `bash` isolé.
- **Durcissement sandbox** : utilisateur non-root (UID aligné hôte),
  `--cap-drop ALL`, `no-new-privileges`, FS racine en lecture seule + tmpfs,
  limites CPU/mémoire/pids, réseau coupé par défaut (opt-in `allow_network`).
- **Agent** : boucle de génération streaming via Ollama (partagé), tool calling,
  snapshot workspace + `AGENTS.md`, panneau raisonnement, sélecteur de modèle.
- **Approbations persistantes** : `PermissionRequest` en base, résolues via
  WebSocket ou REST, survivent à la reconnexion (timeout 600 s).
- **Exécution asynchrone** : pulls Ollama et provisioning des workspaces via
  Celery (progression par polling) ; exécution des agents via Celery avec
  **reprise après crash** (`acks_late`, idempotence `run_id`).
- **Orchestration multi-workers** : verrou et annulation partagés via Redis
  (`apps/agents/orchestrator.py`).
- **Frontend React** (UI violette reprise de l'app desktop) : login/SSO, org →
  workspace → session, chat streaming 3 colonnes, approbation de commandes,
  gestion des modèles Ollama (pull avec progression).
- **CI/CD** : workflow de tests (`ci.yml`) et de release d'images Docker sur
  GHCR (`release.yml`).

### Notes

- Le backend, le frontend et le sandbox sont packagés en images Docker
  (production : `daphne` + `nginx` + whitenoise).
- Le SSO OIDC est vérifié jusqu'à la redirection IdP ; le callback reste à
  valider contre un IdP réel (Entra ID / Okta / Keycloak).

[0.1.0]: https://github.com/LudovicBoudi/Cyonima-code-agent-server/releases/tag/v0.1.0
