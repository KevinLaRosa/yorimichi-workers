#!/bin/bash

# Script d'installation de pyenv pour gérer plusieurs versions de Python
# Équivalent de nvm pour Python

echo "🐍 Installation de pyenv..."

# 1. Installer les dépendances nécessaires
echo "📦 Installation des dépendances..."
sudo apt update
sudo apt install -y make build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
    libffi-dev liblzma-dev git

# 2. Installer pyenv
echo "📥 Installation de pyenv..."
curl https://pyenv.run | bash

# 3. Configurer le shell (.bashrc ou .zshrc)
echo "⚙️ Configuration du shell..."

# Ajouter pyenv au PATH
cat << 'EOF' >> ~/.bashrc

# Pyenv configuration
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
EOF

echo "✅ Pyenv installé!"
echo ""
echo "🔄 Pour activer pyenv, exécutez:"
echo "   source ~/.bashrc"
echo ""
echo "📝 Commandes utiles:"
echo "   pyenv install --list       # Lister les versions disponibles"
echo "   pyenv install 3.11.5       # Installer Python 3.11.5"
echo "   pyenv install 3.12.0       # Installer Python 3.12.0"
echo "   pyenv versions             # Voir les versions installées"
echo "   pyenv global 3.11.5        # Définir la version globale"
echo "   pyenv local 3.11.5         # Définir la version pour ce projet"
echo ""
echo "🚀 Installation pour Yorimichi:"
echo "   pyenv install 3.11.5"
echo "   pyenv local 3.11.5"
echo "   python -m venv venv"
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"
echo "   pip install jageocoder"