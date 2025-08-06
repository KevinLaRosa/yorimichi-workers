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

## 🗾 Phase 2 : Géocoding et Enrichissement avec Foursquare
**Status: EN COURS** ⚠️ (jageocoder ne fonctionne pas, pivot vers Foursquare)
**Temps estimé: 3-4 heures**
**Solution: Utiliser Foursquare API pour géocoding ET enrichissement simultané**

### ⚠️ PROBLÈME IDENTIFIÉ
- **Noms japonais non scrapés** depuis Tokyo Cheapo (oubli lors du scraping initial)
- **Solution**: Foursquare fonctionne bien avec noms anglais + matching par proximité

### Setup Foursquare (GRATUIT - $200/mois free tier)
- [ ] Créer compte sur https://foursquare.com/developers/
- [ ] Obtenir API Key
- [ ] Ajouter dans .env : `FOURSQUARE_API_KEY=your_key`

### Exécution du géocoding + enrichissement
- [ ] Test sur échantillon :
  ```bash
  python enrich_with_foursquare.py --limit 10 --test
  ```
- [ ] Géocoder les POIs sans coordonnées :
  ```bash
  python enrich_with_foursquare.py --only-missing-coords
  ```
- [ ] Enrichir TOUS les POIs avec métadonnées :
  ```bash
  python enrich_with_foursquare.py --platform tokyo_cheapo
  ```

### Vérifications SQL
```sql
-- POIs sans coordonnées
SELECT COUNT(*) FROM place 
WHERE platform = 'tokyo_cheapo' 
AND (latitude IS NULL OR latitude = 0);

-- POIs enrichis avec Foursquare
SELECT COUNT(*) FROM place 
WHERE platform = 'tokyo_cheapo' 
AND fsq_id IS NOT NULL;
```

### Données récupérées via Foursquare
- ✅ Coordonnées GPS précises
- ✅ Photos (jusqu'à 10 par lieu)
- ✅ Rating et price tier
- ✅ Horaires structurés
- ✅ Numéro de téléphone
- ✅ Site web
- ✅ Tips/Avis utilisateurs
- ✅ Catégories et tags
- ✅ Statut vérifié

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

## 🎯 Phase 4 : ~~Enrichissement avec Foursquare API~~ ✅ FUSIONNÉ AVEC PHASE 2
**Status: FUSIONNÉ** avec Phase 2 (géocoding + enrichissement simultané)
**Note**: Le script `enrich_with_foursquare.py` fait déjà tout :
- Géocoding des adresses manquantes
- Enrichissement avec photos, ratings, horaires, etc.
- Matching intelligent même sans noms japonais

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

1. **Finir le scraping Tokyo Cheapo** ✅ FAIT (1322 POIs scrapés)
2. **Géocoding + Enrichissement Foursquare** 🔄 EN COURS
   - Setup compte Foursquare
   - Lancer `enrich_with_foursquare.py`
   - Récupérer coords GPS + photos + ratings + horaires
3. **Migration schéma DB** 📊 À FAIRE
   - Ajouter colonnes manquantes (fsq_id, rating, photos, etc.)
4. **Gestion des images** 📸 À PLANIFIER

---

*Document créé le 05/08/2025*
*À mettre à jour régulièrement avec l'avancement*