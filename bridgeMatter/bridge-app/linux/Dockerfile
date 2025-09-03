FROM ubuntu:22.04

# Dépendances de build
RUN apt-get update && apt-get install -y \
    git gcc g++ python3 python3-venv python3-dev \
    pkg-config libssl-dev libdbus-1-dev libglib2.0-dev \
    ninja-build unzip curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail dans le conteneur
WORKDIR /opt/connectedhomeip

# On ne copie pas le code ici -> on le "montera" via docker-compose volume
CMD ["bash"]
FROM ubuntu:22.04

# Dépendances de build
RUN apt-get update && apt-get install -y \
    git gcc g++ python3 python3-venv python3-dev \
    pkg-config libssl-dev libdbus-1-dev libglib2.0-dev \
    ninja-build unzip curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail dans le conteneur
WORKDIR /opt/connectedhomeip

# On ne copie pas le code ici -> on le "montera" via docker-compose volume
CMD ["bash"]
