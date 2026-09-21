# Sandbox d'exécution pour l'agent de code.
# Conteneur jetable : un conteneur = un workspace. Les fichiers du workspace
# sont montés depuis l'hôte en bind-mount sur /workspace.

FROM python:3.12-slim

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

WORKDIR /workspace

# L'utilisateur par défaut est root dans le sandbox : le conteneur est jetable
# et déjà isolé par Docker. Pour un durcissement supplémentaire, créer un
# utilisateur non-root et le déclarer via USER.
CMD ["sleep", "infinity"]
