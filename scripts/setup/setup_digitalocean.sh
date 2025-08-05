#!/bin/bash
# Script de setup automatique pour Digital Ocean Droplet
# À exécuter après connexion SSH au droplet

echo "🚀 Setup Yorimichi Crawler sur Digital Ocean"

# 1. Mise à jour système
echo "📦 Mise à jour des paquets..."
sudo apt update && sudo apt upgrade -y

# 2. Installation Python et Git
echo "🐍 Installation Python 3.11..."
sudo apt install -y python3.11 python3.11-venv python3-pip git

# 3. Clone du repository
echo "📥 Clonage du repository..."
git clone https://github.com/YOUR_USERNAME/yorimichi.git
cd yorimichi

# 4. Environnement virtuel Python
echo "🔧 Création de l'environnement virtuel..."
python3.11 -m venv venv
source venv/bin/activate

# 5. Installation des dépendances
echo "📚 Installation des dépendances..."
pip install --upgrade pip
pip install -r requirements.txt

# 6. Configuration
echo "⚙️ Configuration..."
echo "IMPORTANT: Créez maintenant votre fichier .env avec:"
echo "nano .env"
echo ""
echo "Copiez-collez ceci et remplacez par vos vraies clés:"
echo "----------------------------------------"
cat .env.example
echo "----------------------------------------"
echo ""
echo "Appuyez sur Ctrl+X, puis Y pour sauvegarder"
echo ""
read -p "Appuyez sur Entrée quand le .env est configuré..."

# 7. Lancement
echo "🎯 Prêt à lancer! Utilisez:"
echo "python main_crawler.py"
echo ""
echo "💡 Astuce: Utilisez 'screen' pour que ça continue si SSH se déconnecte:"
echo "screen -S crawler"
echo "python main_crawler.py"
echo "(Ctrl+A puis D pour détacher)"
echo "(screen -r crawler pour revenir)"