# Guide des Services de Scraping - Tokyo Cheapo Crawler

## 🎯 Configuration Multi-Service

Le crawler supporte maintenant **ScrapingBee** (par défaut) et **ScraperAPI**.

### 📋 Options de Configuration

1. **Variable d'environnement** (recommandé)
   ```bash
   export SCRAPING_SERVICE=scrapingbee  # ou scraperapi
   ```

2. **Argument CLI**
   ```bash
   python main_crawler_tokyo_cheapo.py --service scraperapi
   ```

3. **Fichier .env.local**
   ```bash
   SCRAPING_SERVICE=scrapingbee
   SCRAPINGBEE_API_KEY=votre_cle_scrapingbee
   # ou
   SCRAPING_SERVICE=scraperapi
   SCRAPERAPI_KEY=votre_cle_scraperapi
   ```

### 🚀 Exemples d'Utilisation

#### ScrapingBee (par défaut)
```bash
# Utilise ScrapingBee par défaut
python main_crawler_tokyo_cheapo.py

# Ou explicitement
python main_crawler_tokyo_cheapo.py --service scrapingbee

# Avec variable d'environnement
SCRAPING_SERVICE=scrapingbee python main_crawler_tokyo_cheapo.py
```

#### ScraperAPI
```bash
# Via argument CLI
python main_crawler_tokyo_cheapo.py --service scraperapi

# Via variable d'environnement
export SCRAPING_SERVICE=scraperapi
python main_crawler_tokyo_cheapo.py

# One-liner
SCRAPING_SERVICE=scraperapi python main_crawler_tokyo_cheapo.py --limit 100
```

### 📊 Comparaison des Services

| Service | Requêtes/mois | Prix | Avantages |
|---------|---------------|------|-----------|
| **ScrapingBee** | 50,000 | $49 | Interface simple, screenshots |
| **ScraperAPI** | 100,000 | $49 | 2x plus de requêtes, sessions |

### 🔑 Configuration des Clés API

#### ScrapingBee
```bash
export SCRAPINGBEE_API_KEY=votre_cle_ici
```

#### ScraperAPI
```bash
export SCRAPERAPI_KEY=votre_cle_ici
# Par défaut : 941de144518cb736f43c2b01632de99a (271 crédits restants)
```

### ✅ Fonctionnalités Communes

Les deux services supportent :
- ✅ Skip automatique des 307 POIs déjà scrapés
- ✅ Proxy japonais
- ✅ Rendering JavaScript
- ✅ Attente du sélecteur `.item-card`

### 📈 Logs

Le service utilisé est affiché au démarrage :
```
📦 Service de scraping: scrapingbee
✅ 307 URLs Tokyo Cheapo déjà scrapées
```

### 💡 Recommandations

- **ScrapingBee** : Si vous avez déjà une clé et êtes familier
- **ScraperAPI** : Pour plus de volume (2x plus de requêtes)
- **Test** : `python main_crawler_tokyo_cheapo.py --service scraperapi --limit 5`

---
*Mis à jour le 4 Août 2025*