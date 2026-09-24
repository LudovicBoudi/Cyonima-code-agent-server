# Sandbox d'exécution pour l'agent de code.
# Conteneur jetable : un conteneur = un workspace. Les fichiers du workspace
# sont montés depuis l'hôte en bind-mount sur /workspace.
#
# Durcissement :
#   - utilisateur non-root `agent` (UID/GID configurables au build, alignés sur
#     l'hôte pour que le bind-mount soit accessible en écriture),
#   - le conteneur est lancé avec `--cap-drop ALL`, `--security-opt
#     no-new-privileges`, FS racine en lecture seule, limites CPU/mémoire/pids
#     et réseau coupé (voir apps/workspaces/sandbox.py).

FROM python:3.12-slim

ARG UID=1000
ARG GID=1000

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        build-essential \
        && rm -rf /var/lib/apt/lists/*

# Node.js (LTS) pour les projets JS/TS
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Utilisateur non-root avec UID/GID alignés sur l'hôte
RUN groupadd -g "${GID}" agent \
    && useradd -m -u "${UID}" -g "${GID}" -s /bin/bash agent

WORKDIR /workspace
RUN mkdir -p /workspace /home/agent && chown -R agent:agent /home/agent

USER agent

CMD ["sleep", "infinity"]
