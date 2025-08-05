# Yorimichi Intelligent Crawler V2

Un agent de collecte intelligent qui parcourt des sites web pour identifier et créer automatiquement des Points d'Intérêt (POI) uniques dans votre base de données Supabase.

## 🎯 Fonctionnalités Principales

- **Crawling Intelligent** : Parcourt automatiquement les sitemaps et identifie les articles pertinents
- **Classification IA** : Utilise GPT-3.5 pour déterminer si un article décrit un POI
- **Reformulation Unique** : Génère des descriptions originales avec GPT-4 pour éviter le plagiat
- **Extraction Structurée** : Extrait automatiquement nom, quartier, résumé et mots-clés
- **Détection de Doublons** : Utilise des embeddings pour éviter les doublons sémantiques
- **Reprise sur Erreur** : Système robuste et idempotent qui peut reprendre où il s'est arrêté
- **Monitoring Complet** : Logs détaillés en base de données pour suivre l'activité

## 🚀 Installation

### 1. Prérequis

- Python 3.8+
- Un projet Supabase configuré
- Des clés API pour OpenAI et ScrapingBee

### 2. Installation des dépendances

```bash
pip install -r requirements.txt
```

### 3. Configuration de la base de données

Exécutez le script SQL fourni dans votre projet Supabase :

```bash
# Dans l'éditeur SQL de Supabase, copiez-collez le contenu de database_setup.sql
```

### 4. Configuration des variables d'environnement

```bash
cp .env.example .env
# Éditez .env avec vos vraies clés API
```

## 📋 Configuration

Le crawler est configuré par défaut pour :
- Site cible : Tokyo Cheapo
- Modèles IA : GPT-3.5 pour la classification, GPT-4 pour la reformulation
- Délai entre requêtes : 1 seconde
- Logs de progression : toutes les 25 URLs

Vous pouvez modifier ces paramètres dans la classe `YorimichiIntelligentCrawler`.

## 🏃 Utilisation

### Lancement simple

```bash
python main_crawler.py
```

### Monitoring en temps réel

Pendant l'exécution, le crawler :
- Affiche les logs dans la console
- Enregistre les logs dans `yorimichi_crawler.log`
- Sauvegarde l'état dans la base de données

### Suivi dans Supabase

```sql
-- Voir la progression globale
SELECT status, COUNT(*) 
FROM processed_urls 
GROUP BY status;

-- Voir les logs récents
SELECT * FROM agent_logs 
ORDER BY created_at DESC 
LIMIT 20;

-- Voir les POIs créés (brouillons)
SELECT * FROM locations 
WHERE is_active = false 
ORDER BY created_at DESC;
```

## 🔄 Reprise sur Erreur

Le crawler est conçu pour être relancé sans risque :
- Il reprend automatiquement où il s'est arrêté
- Les URLs déjà traitées ne sont pas re-téléchargées
- Les erreurs n'arrêtent pas le processus global

## 📊 Structure des Données

### Table `locations` (POI créés)
- `name` : Nom du lieu extrait
- `description` : Description unique reformulée
- `is_active` : false (brouillons par défaut)
- `source_url` : URL originale
- `source_name` : "Tokyo Cheapo"
- `features` : Données additionnelles (quartier, mots-clés)

### Table `processed_urls`
- `url` : URL traitée
- `status` : success, failed, skipped_not_a_poi, skipped_duplicate
- `processed_at` : Timestamp du traitement

### Table `agent_logs`
- Logs détaillés de l'activité du crawler
- Statuts : STARTED, RUNNING, SUCCESS, ERROR
- Détails JSON pour le debugging

## 🛡️ Gestion des Erreurs

Le crawler gère gracieusement :
- Timeouts réseau
- Erreurs API (OpenAI, ScrapingBee)
- Pages mal formées
- Réponses IA inattendues

Chaque erreur est loggée sans arrêter le processus global.

## 💰 Optimisation des Coûts

- Utilise GPT-3.5 (moins cher) pour la classification initiale
- Limite la taille du texte envoyé aux APIs
- Cache les embeddings dans la base
- Évite de retraiter les URLs déjà vues

## 🔧 Personnalisation

Pour adapter le crawler à d'autres sites :

1. Modifiez `sitemap_url` dans `__init__`
2. Ajustez les sélecteurs BeautifulSoup dans `extract_text_content`
3. Personnalisez les prompts GPT selon vos besoins
4. Adaptez la structure de données extraites

## 📈 Performance

Sur un site typique :
- ~30-60 secondes par URL (incluant tous les appels API)
- ~100-200 POIs/heure selon la complexité
- Coût estimé : ~0.10-0.20$ par POI créé

## 🐛 Debugging

En cas de problème :

1. Vérifiez les logs console et fichier
2. Consultez la table `agent_logs` dans Supabase
3. Vérifiez vos quotas API (OpenAI, ScrapingBee)
4. Testez avec une seule URL en mode debug

## 📝 License

Ce projet fait partie de Yorimichi et suit les mêmes conditions de licence.