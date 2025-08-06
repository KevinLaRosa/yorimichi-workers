# Guide Pyenv - Gestion Multi-Version Python

## 🎯 Qu'est-ce que Pyenv ?

Pyenv est l'équivalent de **nvm** pour Python. Il permet de :
- Installer et gérer plusieurs versions de Python
- Changer facilement entre les versions
- Définir une version par projet
- Éviter les conflits de versions

## 📦 Installation

### Option 1 : Script automatique
```bash
bash scripts/setup/install_pyenv.sh
source ~/.bashrc
```

### Option 2 : Installation manuelle
```bash
# Installer les dépendances
sudo apt update
sudo apt install -y make build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
    libffi-dev liblzma-dev git

# Installer pyenv
curl https://pyenv.run | bash

# Ajouter au .bashrc
echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc

# Recharger le shell
source ~/.bashrc
```

## 🚀 Utilisation

### Commandes de base

```bash
# Lister les versions disponibles
pyenv install --list | grep " 3\."

# Installer une version spécifique
pyenv install 3.11.5
pyenv install 3.12.0
pyenv install 3.10.13

# Voir les versions installées
pyenv versions

# Définir la version globale (système)
pyenv global 3.11.5

# Définir la version locale (projet)
cd ~/yorimichi-workers
pyenv local 3.11.5  # Crée un fichier .python-version

# Vérifier la version active
python --version
pyenv version
```

### Workflow pour Yorimichi

```bash
# 1. Aller dans le projet
cd ~/yorimichi-workers

# 2. Installer Python 3.11 (compatible avec jageocoder)
pyenv install 3.11.5

# 3. Définir comme version locale
pyenv local 3.11.5

# 4. Créer l'environnement virtuel
python -m venv venv

# 5. Activer le venv
source venv/bin/activate

# 6. Installer les dépendances
pip install -r requirements.txt
pip install jageocoder

# 7. Lancer le script
python fix_all_geocoding.py --test --limit 5
```

## 🔄 Changer de version Python

```bash
# Pour un projet spécifique
cd /path/to/project
pyenv local 3.10.13  # Utilise Python 3.10 pour ce projet

# Globalement
pyenv global 3.12.0  # Utilise Python 3.12 par défaut

# Temporairement (session shell)
pyenv shell 3.9.18   # Utilise Python 3.9 pour cette session
```

## 📝 Fichier .python-version

Pyenv crée automatiquement un fichier `.python-version` quand vous utilisez `pyenv local`. Ce fichier :
- Définit la version Python pour le projet
- Est automatiquement détecté par pyenv
- Devrait être ajouté au `.gitignore` (préférence personnelle)

Exemple :
```
3.11.5
```

## 🎨 Comparaison avec nvm

| nvm | pyenv | Description |
|-----|-------|-------------|
| `nvm install 18` | `pyenv install 3.11.5` | Installer une version |
| `nvm use 18` | `pyenv local 3.11.5` | Utiliser une version |
| `nvm ls` | `pyenv versions` | Lister les versions installées |
| `nvm ls-remote` | `pyenv install --list` | Lister les versions disponibles |
| `.nvmrc` | `.python-version` | Fichier de configuration |
| `nvm alias default 18` | `pyenv global 3.11.5` | Version par défaut |

## 🛠️ Dépannage

### Pyenv ne trouve pas les commandes
```bash
# Vérifier que pyenv est dans le PATH
echo $PATH | grep pyenv

# Recharger la configuration
source ~/.bashrc
```

### Les builds échouent
```bash
# Installer les dépendances manquantes
sudo apt install -y build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev
```

### Version Python pas disponible
```bash
# Mettre à jour pyenv
cd ~/.pyenv && git pull
```

## 🔗 Alternatives

Si pyenv ne convient pas, voici d'autres options :

1. **deadsnakes PPA** (Ubuntu)
   ```bash
   sudo add-apt-repository ppa:deadsnakes/ppa
   sudo apt update
   sudo apt install python3.11
   ```

2. **conda/miniconda** - Gestion d'environnements Python
   ```bash
   wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
   bash Miniconda3-latest-Linux-x86_64.sh
   ```

3. **asdf** - Gestionnaire de versions multi-langage
   ```bash
   git clone https://github.com/asdf-vm/asdf.git ~/.asdf
   echo '. "$HOME/.asdf/asdf.sh"' >> ~/.bashrc
   asdf plugin add python
   asdf install python 3.11.5
   ```

## 📚 Ressources

- [Documentation officielle pyenv](https://github.com/pyenv/pyenv)
- [pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv)
- [Comparaison des gestionnaires Python](https://realpython.com/intro-to-pyenv/)