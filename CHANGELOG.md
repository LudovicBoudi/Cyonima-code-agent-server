# Changelog

Toutes les évolutions notables de Cyonima Code Agent Server sont consignées ici.
Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le
versionnage [SemVer](https://semver.org/lang/fr/).

## [Unreleased]

### Ajouté

- **Catalogue de modèles** intégré à la page « Modèles Ollama » : même sélection
  de modèles recommandés que le client lourd (`qwen3`, `ornith-1.5`, `gemma4`,
  `granite4.2`…), avec filtrage, statut installé et bouton d'installation via
  `ollama pull` (`GET /api/ollama/catalog/`).
- **Administration (nouvel onglet « Paramètres »)** : configuration serveur
  depuis l'UI, pour les utilisateurs staff.
  - **HTTPS** : redirection HTTP→HTTPS, en-tête HSTS et cookies `Secure`
    appliqués à chaud via un middleware piloté par la base (`SystemConfig`).
    Génération d'un **certificat auto-signé** (RSA 2048) et d'un site **nginx**
    prêt à monter, écrits dans `backend/data/tls/`. Inactif sur `localhost` en
    dev pour ne pas casser le développement.
  - **LDAP / Active Directory** : boîte de configuration (URI, DN de liaison,
    base, filtre, StartTLS…) avec **test de connexion** avant sauvegarde.
    Backend d'authentification `LdapBackend` (via `ldap3`) : bind service →
    recherche → vérification du mot de passe de l'utilisateur. Le compte local
    est créé automatiquement à la première connexion (login par email) ; le mot
    de passe utilisateur n'est **jamais** stocké.

### Modifié

- **Procédure d'installation documentée** : nouveau guide détaillé
  `docs/INSTALL.md` (prérequis, `.env`, dev SQLite sans Docker, dev Docker,
  sandbox, HTTPS/LDAP depuis l'admin, production, dépannage) ; le README
  renvoie vers ce guide et schématise le démarrage rapide.
- **Session d'authentification plus longue** : le JWT d'accès passe de 5 min à
  12 h, le refresh à 7 jours avec rotation automatique. Le frontend renouvelle
  le token à la volée via `/api/auth/refresh/` lorsqu'une requête retourne 401,
  au lieu de déconnecter immédiatement.
- **Auto-scroll des sessions** : le fil de conversation ne défile plus de force
  si l'utilisateur remonte lire un message ; il ne suit le bas que lorsqu'on y
  est déjà, avec un défilement instantané pendant le streaming.
- **Modèles thinking qui « s'arrêtent »** (ex. `ornith-1.5:9b`) : lorsqu'un tour
  ne produit que du raisonnement interne puis se termine sans contenu ni appel
  d'outil, l'agent relance automatiquement la génération sans mode thinking. Si
  la réponse reste vide, un message clair est renvoyé au lieu d'un message
  assistant vide.
- **Permissions par chemin** : la lecture/écriture de fichiers **dans** le
  répertoire de travail est auto-approuvée (aucune interaction). Tout accès
  **hors** du workspace (chemin absolu, ex. `/tmp`) déclenche une approbation ;
  ces accès sont confinés aux racines externes autorisées
  (`WORKSPACE_EXTERNAL_ROOTS`, défaut `/tmp`). `bash` reste systématiquement
  soumis à approbation.
- **Bouton arrêter** : en développement, le canal WS utilise
  `InMemoryChannelLayer` par défaut (Redis facultatif) — l'annulation du
  raisonnement en cours atteint bien le client.
- **Inscription publique fermée** : plus de création de compte sur la page de
  connexion ; seuls les admins créent des comptes depuis l'application
  (`/api/auth/admin/users/`).
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
