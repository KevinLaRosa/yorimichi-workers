# CLAUDE.md - Documentation des changements par Claude

## 📅 4 Août 2025 - Support Multi-Service (ScrapingBee + ScraperAPI)

### 🔄 Changements effectués

1. **Support multi-service de scraping**
   - Ajout du choix entre ScrapingBee et ScraperAPI dans `main_crawler_tokyo_cheapo.py`
   - ScrapingBee reste le service par défaut
   - Configuration via `SCRAPING_SERVICE` env var ou `--service` CLI
   - ScraperAPI offre 100k requêtes/mois vs 50k pour le même prix

2. **Skip automatique des URLs déjà scrapées**
   - Charge les 307 URLs Tokyo Cheapo existantes au démarrage
   - Skip instantané si URL déjà dans la base (économise des crédits API)
   - Ajoute les nouvelles URLs après sauvegarde réussie

3. **Paramètres API mis à jour**
   ```python
   # Avant (ScrapingBee)
   'render_js': 'true'
   'premium_proxy': 'true'
   
   # Après (ScraperAPI)
   'render': 'true'
   'premium': 'true'
   ```

### 📊 Impact

- **307 POIs déjà scrapés** → seront automatiquement skippés
- **1015 POIs restants** (au lieu de 1322 au total)
- **271 crédits ScraperAPI disponibles**
- **Économie estimée** : 307 requêtes API (~$0.15)

### 🚀 Utilisation

```bash
# ScrapingBee (par défaut)
python main_crawler_tokyo_cheapo.py

# ScraperAPI
python main_crawler_tokyo_cheapo.py --service scraperapi

# Avec variable d'environnement
SCRAPING_SERVICE=scraperapi python main_crawler_tokyo_cheapo.py

# Limiter aux crédits gratuits
python main_crawler_tokyo_cheapo.py --service scraperapi --limit 271

# Mode test
python main_crawler_tokyo_cheapo.py --service scrapingbee --test
```

### 📝 Notes techniques

- La validation d'environnement exige `SCRAPINGBEE_API_KEY` seulement si ScrapingBee est utilisé
- ScrapingBee reste le service par défaut pour la compatibilité
- Les logs afficheront "⏭️ URL déjà scrapée" pour chaque skip
- Compatible avec toutes les options existantes du crawler

### ⚠️ À surveiller

- Vérifier que ScraperAPI gère bien le JavaScript de Tokyo Cheapo
- Les crédits restants après 271 requêtes
- Performance comparée à ScrapingBee

---
*Modifié par Claude le 4 Août 2025*