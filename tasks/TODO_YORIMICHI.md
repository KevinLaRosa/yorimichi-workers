# 📋 TODO YORIMICHI - Plan de développement complet

## 🚀 Phase 1 : Finalisation du Scraping Tokyo Cheapo
**Status: EN COURS**
**Deadline estimée: 1-2 jours**

- [ ] Terminer le scraping des ~1600 POIs restants
  - [ ] Restaurants (`--target restaurants`)
  - [ ] Attractions (`--target attractions`)
  - [ ] Hébergements (`--target accommodation`)
- [ ] Surveiller les logs pour détecter les erreurs
- [ ] Vérifier dans Supabase le nombre total de POIs créés
- [ ] Noter les URLs qui ont échoué pour retry éventuel

---

## 🗾 Phase 2 : Correction des Coordonnées GPS
**Status: À FAIRE**
**Temps estimé: 2-3 heures**

### Installation et préparation
- [ ] Installer jageocoder : `pip install jageocoder`
- [ ] Tester la connexion au serveur Jageocoder

### Exécution du fix
- [ ] Lancer le script de geocoding :
  ```bash
  python fix_all_geocoding.py --platform tokyo_cheapo
  ```
- [ ] Vérifier les POIs sans coordonnées avant :
  ```sql
  SELECT COUNT(*) FROM place 
  WHERE platform = 'tokyo_cheapo' 
  AND (latitude IS NULL OR longitude IS NULL OR latitude = 0);
  ```
- [ ] Analyser les logs pour identifier les adresses problématiques
- [ ] Vérifier les POIs corrigés après :
  ```sql
  SELECT COUNT(*) FROM place 
  WHERE platform = 'tokyo_cheapo' 
  AND latitude IS NOT NULL AND longitude IS NOT NULL;
  ```

---

## 🔄 Phase 3 : Migration du Schéma de Base de Données
**Status: À FAIRE**
**Temps estimé: 1 jour**

### 3.1 Ajout des colonnes manquantes essentielles
- [ ] Créer un backup de la base avant modifications
- [ ] Exécuter les ALTER TABLE pour ajouter :
  ```sql
  -- Identifiants externes
  ALTER TABLE place ADD COLUMN fsq_id VARCHAR(50) UNIQUE;
  ALTER TABLE place ADD COLUMN google_place_id VARCHAR(255);
  
  -- Métriques et évaluations
  ALTER TABLE place ADD COLUMN rating DECIMAL(3,1);
  ALTER TABLE place ADD COLUMN price_tier INTEGER CHECK (price_tier BETWEEN 1 AND 4);
  ALTER TABLE place ADD COLUMN popularity DECIMAL(3,2);
  ALTER TABLE place ADD COLUMN verified BOOLEAN DEFAULT FALSE;
  
  -- Données structurées
  ALTER TABLE place ADD COLUMN photos JSONB DEFAULT '[]'::jsonb;
  ALTER TABLE place ADD COLUMN hours JSONB;
  ALTER TABLE place ADD COLUMN stats JSONB;
  ALTER TABLE place ADD COLUMN tips JSONB DEFAULT '[]'::jsonb;
  
  -- Contact et social
  ALTER TABLE place ADD COLUMN phone VARCHAR(50);
  ALTER TABLE place ADD COLUMN website VARCHAR(500);
  ALTER TABLE place ADD COLUMN social_links JSONB;
  
  -- Métadonnées
  ALTER TABLE place ADD COLUMN tastes TEXT[];
  ALTER TABLE place ADD COLUMN amenities TEXT[];
  ALTER TABLE place ADD COLUMN payment_methods TEXT[];
  ```

### 3.2 Migration des données existantes
- [ ] Convertir les horaires texte en format structuré :
  ```python
  # Script de migration des horaires
  # Convertir "Mon-Fri: 9:00-21:00" vers format JSON structuré
  ```
- [ ] Migrer les features existantes vers les nouvelles colonnes
- [ ] Valider l'intégrité des données après migration

### 3.3 Création des index pour performance
- [ ] Index sur fsq_id pour matching rapide
- [ ] Index sur rating pour tri
- [ ] Index GIN sur hours->>'open_now' pour filtrage
- [ ] Index géospatial si pas déjà présent

---

## 🎯 Phase 4 : Enrichissement avec Foursquare API
**Status: À PLANIFIER**
**Temps estimé: 2-3 jours**
**Budget: GRATUIT (dans le free tier $200/mois)**

### 4.1 Setup Foursquare
- [ ] Créer un compte développeur Foursquare
- [ ] Obtenir les clés API
- [ ] Configurer les variables d'environnement :
  ```bash
  FOURSQUARE_API_KEY=xxx
  FOURSQUARE_API_SECRET=xxx
  ```

### 4.2 Développement du script d'enrichissement
- [ ] Créer `enrich_with_foursquare.py`
- [ ] Implémenter le matching par coordonnées + nom
- [ ] Gérer les rate limits (50 req/sec)
- [ ] Logger les matches réussis/échoués
- [ ] Système de checkpoint pour reprise après interruption

### 4.3 Données à récupérer prioritairement
- [ ] **Photos** (max 10 par lieu)
- [ ] **Rating** (note sur 10)
- [ ] **Price tier** (1-4)
- [ ] **Horaires structurés**
- [ ] **Numéro de téléphone**
- [ ] **Site web**
- [ ] **Tips/Avis** (top 5 plus récents)
- [ ] **Stats** (nombre de photos, tips, checkins)
- [ ] **Verified status**

### 4.4 Exécution de l'enrichissement
- [ ] Test sur 100 POIs d'abord
- [ ] Vérifier la qualité des matches
- [ ] Lancer sur tous les POIs Tokyo Cheapo
- [ ] Calculer le coût API utilisé vs free tier

---

## 📸 Phase 5 : Gestion des Images
**Status: À PLANIFIER**
**Temps estimé: 2 jours**

### 5.1 Stockage des images
- [ ] Configurer un bucket Supabase Storage
- [ ] Ou utiliser un CDN externe (Cloudinary, etc.)
- [ ] Définir la stratégie de cache

### 5.2 Traitement des images
- [ ] Script pour télécharger les photos Foursquare
- [ ] Redimensionnement en plusieurs tailles :
  - Thumbnail (150x150)
  - Card (400x300)
  - Full (1200x900)
- [ ] Optimisation (WebP, compression)
- [ ] Mise à jour des URLs dans la base

---

## 🔍 Phase 6 : Enrichissement avec Google Places (Optionnel)
**Status: À ÉVALUER**
**Budget: $200/mois free tier**

### Données complémentaires à récupérer
- [ ] Reviews Google
- [ ] Photos supplémentaires
- [ ] Popular times (affluence par heure)
- [ ] Accessibility info
- [ ] Live busyness

---

## 🎨 Phase 7 : Optimisations et Qualité
**Status: À PLANIFIER**
**Temps estimé: 1 semaine**

### 7.1 Qualité des données
- [ ] Déduplications des POIs similaires
- [ ] Standardisation des adresses
- [ ] Validation des coordonnées GPS
- [ ] Nettoyage des descriptions (remove HTML, etc.)
- [ ] Normalisation des catégories

### 7.2 Performance
- [ ] Optimisation des requêtes SQL
- [ ] Mise en place du cache Redis
- [ ] CDN pour les images
- [ ] Pagination optimisée

### 7.3 Search et filtres
- [ ] Index full-text search en japonais
- [ ] Filtres par :
  - [ ] Ouvert maintenant
  - [ ] Distance
  - [ ] Prix
  - [ ] Rating
  - [ ] Catégorie
- [ ] Recherche par quartier/station

---

## 🚀 Phase 8 : Features Avancées
**Status: FUTUR**

### 8.1 Système de recommandation
- [ ] Algorithme de recommandation basé sur :
  - Historique utilisateur
  - Similarité des lieux
  - Popularité
  - Heure de la journée

### 8.2 Itinéraires intelligents
- [ ] Génération d'itinéraires optimisés
- [ ] Prise en compte des horaires d'ouverture
- [ ] Temps de transport entre POIs
- [ ] Suggestions contextuelles

### 8.3 Features sociales
- [ ] Système de favoris utilisateur
- [ ] Partage d'itinéraires
- [ ] Reviews utilisateurs
- [ ] Photos utilisateurs

---

## 📊 Métriques à Suivre

### KPIs Data
- [ ] Nombre total de POIs
- [ ] POIs avec coordonnées valides (%)
- [ ] POIs avec photos (%)
- [ ] POIs avec horaires structurés (%)
- [ ] POIs enrichis Foursquare (%)
- [ ] Qualité du matching Foursquare

### KPIs Techniques
- [ ] Temps de réponse API
- [ ] Taux d'erreur
- [ ] Utilisation stockage
- [ ] Coûts API mensuels

---

## 🐛 Bugs Connus à Corriger

- [ ] Division par zéro dans le crawler quand 0 POIs
- [ ] Géocoding qui échoue sur certaines adresses japonaises
- [ ] Timeout sur certaines pages Tokyo Cheapo
- [ ] Encodage caractères japonais dans certains cas

---

## 📝 Documentation à Créer

- [ ] README du projet avec setup complet
- [ ] Documentation API
- [ ] Guide de contribution
- [ ] Architecture technique
- [ ] Procédures de maintenance

---

## 🔧 Scripts Utilitaires à Développer

- [ ] Script de backup automatique Supabase
- [ ] Script de monitoring des API externes
- [ ] Script de rapport hebdomadaire (nouveaux POIs, etc.)
- [ ] Script de nettoyage des données orphelines
- [ ] Script de test de santé de la base

---

## 💡 Idées pour Plus Tard

- [ ] Intégration avec Instagram API pour photos récentes
- [ ] Scraping de Tabelog (site japonais de restaurants)
- [ ] Intégration météo pour suggestions contextuelles
- [ ] Mode hors-ligne avec sync
- [ ] Application mobile native
- [ ] Multi-langue (EN, JP, FR, CN, KR)
- [ ] Partenariats avec blogs voyage

---

## 📅 Planning Suggéré

**Semaine 1** (En cours)
- Finaliser scraping Tokyo Cheapo
- Corriger coordonnées GPS

**Semaine 2**
- Migration schéma base de données
- Début enrichissement Foursquare

**Semaine 3**
- Finaliser enrichissement
- Gestion des images

**Semaine 4**
- Optimisations
- Tests qualité
- Documentation

**Mois 2+**
- Features avancées
- Enrichissements additionnels
- Scaling

---

## 🎯 Priorités Immédiates

1. **Finir le scraping Tokyo Cheapo** ⏳
2. **Fixer les coordonnées manquantes** 🗾
3. **Enrichir avec Foursquare (photos + ratings)** 📸
4. **Migrer vers horaires structurés** 🕐

---

*Document créé le 05/08/2025*
*À mettre à jour régulièrement avec l'avancement*