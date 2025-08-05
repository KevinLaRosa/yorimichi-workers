# 🌊 Guide Digital Ocean pour Yorimichi Crawler

## Option 1: Droplet One-Shot (Recommandé pour exécution unique)

### 1. Créer un Droplet

```bash
# Via l'interface DO ou CLI :
doctl compute droplet create yorimichi-crawler \
  --size s-1vcpu-1gb \
  --image ubuntu-22-04-x64 \
  --region nyc1
```

**Ou via l'interface web :**
- Ubuntu 22.04
- Basic Plan : 4$/mois (0.006$/heure)
- 1 CPU, 1GB RAM (suffisant)
- N'importe quelle région

### 2. Se connecter au Droplet

```bash
# Attendre 1 minute que le droplet démarre
ssh root@YOUR_DROPLET_IP
```

### 3. Setup automatique

```bash
# Télécharger et exécuter le script de setup
wget https://raw.githubusercontent.com/YOUR_USERNAME/yorimichi/main/setup_digitalocean.sh
chmod +x setup_digitalocean.sh
./setup_digitalocean.sh
```

### 4. Configurer les clés API

```bash
# Le script vous demandera de créer le .env
nano .env

# Collez vos clés :
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-key
OPENAI_API_KEY=sk-...
SCRAPINGBEE_API_KEY=your-key
```

### 5. Lancer le crawler

```bash
# Option A : Lancement simple
cd yorimichi
source venv/bin/activate
python main_crawler.py

# Option B : Avec screen (recommandé)
screen -S crawler
cd yorimichi && source venv/bin/activate
python main_crawler.py
# Ctrl+A puis D pour détacher
# screen -r crawler pour revenir
```

### 6. Monitoring

```bash
# Voir les logs en temps réel
tail -f yorimichi_crawler.log

# Vérifier l'utilisation ressources
htop
```

### 7. Nettoyage (IMPORTANT!)

```bash
# Après le crawl terminé (~10 minutes)
# Télécharger les logs si besoin
scp root@YOUR_DROPLET_IP:~/yorimichi/yorimichi_crawler.log ./

# DÉTRUIRE le droplet pour ne pas payer
doctl compute droplet delete yorimichi-crawler

# Ou via l'interface web : Destroy
```

**💰 Coût total : ~0.001$ (moins d'1 centime!)**

---

## Option 2: Digital Ocean App Platform (Pour automatisation)

### 1. Préparer le repo GitHub

Ajoutez ce fichier à votre repo :

**`.do/app.yaml`** :
```yaml
name: yorimichi-crawler
region: nyc
services:
- name: crawler
  github:
    repo: YOUR_USERNAME/yorimichi
    branch: main
  run_command: python main_crawler.py
  envs:
  - key: SUPABASE_URL
    scope: RUN_TIME
    value: ${SUPABASE_URL}
  - key: SUPABASE_SERVICE_KEY
    scope: RUN_TIME
    value: ${SUPABASE_SERVICE_KEY}
  - key: OPENAI_API_KEY
    scope: RUN_TIME
    value: ${OPENAI_API_KEY}
  - key: SCRAPINGBEE_API_KEY
    scope: RUN_TIME
    value: ${SCRAPINGBEE_API_KEY}
```

### 2. Déployer via DO App Platform

1. Allez sur [Digital Ocean App Platform](https://cloud.digitalocean.com/apps)
2. "Create App" → Connectez GitHub
3. Sélectionnez votre repo yorimichi
4. DO détectera automatiquement le fichier `.do/app.yaml`
5. Configurez les variables d'environnement
6. Deploy!

### 3. Déclencher manuellement

- Via l'interface DO : "Run" button
- Ou créez un endpoint HTTP avec le `server.py`

**💰 Coût : 5$/mois (illimité runs)**

---

## 📊 Comparaison pour votre cas

| Option | Coût | Complexité | Temps setup |
|--------|------|------------|-------------|
| **Droplet One-Shot** | ~0.001$ | Simple | 5 min |
| **App Platform** | 5$/mois | Moyen | 15 min |
| **Local** | 0$ | Très simple | 2 min |

## 🎯 Recommandation finale

Pour **une seule exécution** → **Droplet temporaire**
- Créez, lancez, détruisez
- Coût négligeable
- Serveur dédié stable

```bash
# Timing total :
# 2 min : Créer droplet
# 3 min : Setup
# 10 min : Crawl
# 1 min : Destroy
# = 16 minutes total, ~0.001$
```

C'est la solution idéale : simple, pas chère, et professionnelle !