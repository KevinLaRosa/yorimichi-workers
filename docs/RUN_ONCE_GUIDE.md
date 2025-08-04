# 🚀 Guide d'exécution unique - Tokyo Cheapo Crawler

## 1️⃣ Préparation (5 minutes)

### A. Configuration des clés API
```bash
# Créez votre fichier .env
cp .env.example .env

# Éditez .env avec vos vraies clés :
# - SUPABASE_URL
# - SUPABASE_SERVICE_KEY  
# - OPENAI_API_KEY
# - SCRAPINGBEE_API_KEY
```

### B. Installation Python
```bash
# Installer les dépendances
pip install -r requirements.txt
```

### C. Setup base de données Supabase
1. Allez dans l'éditeur SQL de Supabase
2. Copiez-collez le contenu de `database_setup.sql`
3. Exécutez le script

## 2️⃣ Lancement du crawler

```bash
# C'est parti ! 
python main_crawler.py
```

## 3️⃣ Que va-t-il se passer ?

1. **Découverte** : Le script va récupérer les ~52 articles de Tokyo Cheapo
2. **Traitement** : Pour chaque article :
   - Téléchargement du contenu (ScrapingBee)
   - Classification POI/Non-POI (GPT-3.5)
   - Reformulation unique (GPT-4)
   - Extraction des données (nom, quartier, etc.)
   - Sauvegarde en base comme brouillon
3. **Durée estimée** : ~30-45 minutes pour tout le site
4. **Coût estimé** : ~5-10$ en tokens OpenAI

## 4️⃣ Suivi en temps réel

### Dans le terminal
```
🚀 Démarrage du crawler intelligent Yorimichi
📥 Téléchargement du sitemap: https://tokyocheapo.com/post-sitemap.xml
✅ 52 URLs trouvées dans le sitemap
📋 52 nouvelles URLs à traiter
🔄 Traitement de: https://tokyocheapo.com/entertainment/nakano-broadway/
✅ POI créé: Nakano Broadway
...
```

### Dans Supabase (pendant l'exécution)
```sql
-- Voir la progression
SELECT status, COUNT(*) 
FROM processed_urls 
GROUP BY status;

-- Voir les POIs créés
SELECT name, substring(description, 1, 100) as preview 
FROM locations 
WHERE is_active = false 
ORDER BY created_at DESC;
```

## 5️⃣ Après l'exécution

### Résultats attendus
- ~20-30 POIs créés (beaucoup d'articles ne sont pas des lieux)
- Tous marqués comme `is_active = false` (brouillons)
- Logs complets dans `yorimichi_crawler.log`

### Vérifier les résultats
```sql
-- Stats finales
SELECT 
  (SELECT COUNT(*) FROM locations WHERE source_name = 'Tokyo Cheapo') as pois_created,
  (SELECT COUNT(*) FROM processed_urls WHERE status = 'success') as successful,
  (SELECT COUNT(*) FROM processed_urls WHERE status = 'skipped_not_a_poi') as not_pois,
  (SELECT COUNT(*) FROM processed_urls WHERE status = 'skipped_duplicate') as duplicates;
```

## 6️⃣ Troubleshooting

### Si ça s'arrête en cours de route
Pas de panique ! Relancez simplement :
```bash
python main_crawler.py
```
Le script reprendra automatiquement où il s'est arrêté.

### Erreurs courantes
- **"Rate limit exceeded"** : Attendez 1 minute et relancez
- **"Timeout"** : Normal pour certaines pages, le script continue
- **"Not a POI"** : Normal, beaucoup d'articles sont des guides généraux

## 7️⃣ Nettoyage (optionnel)

Si vous voulez recommencer à zéro :
```sql
-- ⚠️ ATTENTION : Supprime TOUT
DELETE FROM locations WHERE source_name = 'Tokyo Cheapo';
DELETE FROM processed_urls;
DELETE FROM agent_logs WHERE agent_name = 'Intelligent Crawler V2';
```

---

**Temps total estimé : 30-45 minutes**
**Coût total estimé : 5-10$ (tokens OpenAI)**

Bonne collecte ! 🎉