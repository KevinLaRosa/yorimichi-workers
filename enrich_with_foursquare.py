#!/usr/bin/env python3
"""
Script d'enrichissement des POIs avec Foursquare API
- Géocodage des adresses manquantes
- Enrichissement avec métadonnées (photos, ratings, horaires)
- Matching intelligent par nom + localisation
"""

import os
import sys
import json
import time
import logging
import argparse
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import requests
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from urllib.parse import quote

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/foursquare_enrich_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

@dataclass
class FoursquareConfig:
    """Configuration pour l'API Foursquare"""
    api_key: str
    base_url: str = "https://api.foursquare.com/v3"
    rate_limit: int = 50  # requêtes par seconde
    max_results: int = 5  # résultats max par recherche
    
class FoursquareEnricher:
    """Enrichissement des POIs avec Foursquare"""
    
    def __init__(self, config: FoursquareConfig, db_config: Dict):
        self.config = config
        self.db_config = db_config
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': config.api_key,
            'Accept': 'application/json'
        })
        self.stats = {
            'processed': 0,
            'matched': 0,
            'geocoded': 0,
            'enriched': 0,
            'failed': 0,
            'api_calls': 0
        }
        
    def connect_db(self):
        """Connexion à la base de données"""
        return psycopg2.connect(
            host=self.db_config['host'],
            database=self.db_config['database'],
            user=self.db_config['user'],
            password=self.db_config['password'],
            port=self.db_config.get('port', 5432)
        )
        
    def search_place(self, name: str, address: Optional[str] = None, 
                    lat: Optional[float] = None, lon: Optional[float] = None) -> Optional[Dict]:
        """Recherche d'un lieu sur Foursquare"""
        
        # Construire la requête
        params = {
            'limit': self.config.max_results,
            'fields': 'fsq_id,name,location,categories,rating,price,photos,hours,website,tel,verified,stats,tips'
        }
        
        # Stratégie de recherche
        if lat and lon and lat != 0 and lon != 0:
            # Recherche par coordonnées + nom
            params['ll'] = f"{lat},{lon}"
            params['radius'] = 500  # 500m de rayon
            params['query'] = name
            logger.debug(f"Recherche par coordonnées: {name} à {lat},{lon}")
            
        elif address:
            # Recherche par adresse
            params['near'] = f"{address}, Tokyo, Japan"
            params['query'] = name
            logger.debug(f"Recherche par adresse: {name} à {address}")
            
        else:
            # Recherche par nom seul dans Tokyo
            params['near'] = "Tokyo, Japan"
            params['query'] = name
            logger.debug(f"Recherche par nom seul: {name}")
            
        # Appel API
        try:
            url = f"{self.config.base_url}/places/search"
            response = self.session.get(url, params=params)
            self.stats['api_calls'] += 1
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if results:
                    # Prendre le premier résultat (le plus pertinent)
                    best_match = results[0]
                    logger.info(f"✅ Match trouvé: {name} → {best_match.get('name')}")
                    return best_match
                else:
                    logger.warning(f"❌ Aucun résultat pour: {name}")
                    return None
                    
            else:
                logger.error(f"Erreur API {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {e}")
            return None
            
    def get_place_details(self, fsq_id: str) -> Optional[Dict]:
        """Récupère les détails complets d'un lieu"""
        
        try:
            url = f"{self.config.base_url}/places/{fsq_id}"
            params = {
                'fields': 'fsq_id,name,location,categories,rating,price,photos,hours,hours_popular,website,tel,email,verified,date_closed,description,stats,tips,tastes,features'
            }
            
            response = self.session.get(url, params=params)
            self.stats['api_calls'] += 1
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Erreur détails {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur récupération détails: {e}")
            return None
            
    def get_place_photos(self, fsq_id: str, limit: int = 10) -> List[Dict]:
        """Récupère les photos d'un lieu"""
        
        try:
            url = f"{self.config.base_url}/places/{fsq_id}/photos"
            params = {'limit': limit}
            
            response = self.session.get(url, params=params)
            self.stats['api_calls'] += 1
            
            if response.status_code == 200:
                photos = response.json()
                # Construire les URLs complètes
                photo_urls = []
                for photo in photos:
                    photo_url = f"{photo['prefix']}original{photo['suffix']}"
                    photo_urls.append({
                        'url': photo_url,
                        'width': photo.get('width'),
                        'height': photo.get('height'),
                        'created_at': photo.get('created_at')
                    })
                return photo_urls
            else:
                return []
                
        except Exception as e:
            logger.error(f"Erreur récupération photos: {e}")
            return []
            
    def get_place_tips(self, fsq_id: str, limit: int = 5) -> List[Dict]:
        """Récupère les tips/avis d'un lieu"""
        
        try:
            url = f"{self.config.base_url}/places/{fsq_id}/tips"
            params = {'limit': limit, 'sort': 'POPULAR'}
            
            response = self.session.get(url, params=params)
            self.stats['api_calls'] += 1
            
            if response.status_code == 200:
                return response.json()
            else:
                return []
                
        except Exception as e:
            logger.error(f"Erreur récupération tips: {e}")
            return []
            
    def enrich_poi(self, poi: Dict) -> Dict:
        """Enrichit un POI avec les données Foursquare"""
        
        logger.info(f"🔍 Traitement: {poi['name']} (ID: {poi['id']})")
        
        # Rechercher le lieu sur Foursquare
        fsq_place = self.search_place(
            name=poi['name'],
            address=poi.get('address'),
            lat=poi.get('latitude'),
            lon=poi.get('longitude')
        )
        
        if not fsq_place:
            self.stats['failed'] += 1
            return poi
            
        self.stats['matched'] += 1
        
        # Extraire les données
        location = fsq_place.get('location', {})
        
        # Mise à jour des coordonnées si manquantes
        if (not poi.get('latitude') or poi.get('latitude') == 0) and location.get('lat'):
            poi['latitude'] = location['lat']
            poi['longitude'] = location['lng']
            self.stats['geocoded'] += 1
            logger.info(f"📍 Géocodé: {location['lat']}, {location['lng']}")
            
        # Enrichissement des métadonnées
        poi['fsq_id'] = fsq_place.get('fsq_id')
        poi['rating'] = fsq_place.get('rating')
        poi['price_tier'] = fsq_place.get('price')
        poi['verified'] = fsq_place.get('verified', False)
        
        # Catégories
        categories = fsq_place.get('categories', [])
        if categories:
            poi['categories'] = [cat['name'] for cat in categories]
            
        # Coordonnées et adresse formatée
        if location:
            poi['formatted_address'] = location.get('formatted_address')
            poi['cross_street'] = location.get('cross_street')
            poi['postal_code'] = location.get('postcode')
            
        # Contact
        poi['phone'] = fsq_place.get('tel')
        poi['website'] = fsq_place.get('website')
        
        # Horaires
        hours = fsq_place.get('hours')
        if hours:
            poi['hours'] = hours
            poi['open_now'] = hours.get('open_now')
            
        # Stats
        stats = fsq_place.get('stats', {})
        if stats:
            poi['stats'] = stats
            
        # Photos (récupération séparée si fsq_id disponible)
        if poi['fsq_id']:
            photos = self.get_place_photos(poi['fsq_id'])
            if photos:
                poi['photos'] = photos
                logger.info(f"📸 {len(photos)} photos récupérées")
                
            # Tips/Avis
            tips = self.get_place_tips(poi['fsq_id'])
            if tips:
                poi['tips'] = tips
                logger.info(f"💬 {len(tips)} avis récupérés")
                
        # Features/Amenities
        features = fsq_place.get('features', {})
        if features:
            poi['amenities'] = list(features.keys())
            
        self.stats['enriched'] += 1
        
        # Rate limiting
        time.sleep(1 / self.config.rate_limit)
        
        return poi
        
    def update_database(self, poi: Dict) -> bool:
        """Met à jour un POI dans la base de données"""
        
        try:
            conn = self.connect_db()
            cursor = conn.cursor()
            
            # Construire la requête UPDATE
            update_parts = []
            params = []
            
            # Coordonnées
            if poi.get('latitude') and poi['latitude'] != 0:
                update_parts.append("latitude = %s")
                params.append(poi['latitude'])
                update_parts.append("longitude = %s")
                params.append(poi['longitude'])
                
            # Identifiants
            if poi.get('fsq_id'):
                update_parts.append("fsq_id = %s")
                params.append(poi['fsq_id'])
                
            # Métadonnées
            if poi.get('rating'):
                update_parts.append("rating = %s")
                params.append(poi['rating'])
                
            if poi.get('price_tier'):
                update_parts.append("price_tier = %s")
                params.append(poi['price_tier'])
                
            if 'verified' in poi:
                update_parts.append("verified = %s")
                params.append(poi['verified'])
                
            # Contact
            if poi.get('phone'):
                update_parts.append("phone = %s")
                params.append(poi['phone'])
                
            if poi.get('website'):
                update_parts.append("website = %s")
                params.append(poi['website'])
                
            # JSON fields
            if poi.get('photos'):
                update_parts.append("photos = %s")
                params.append(Json(poi['photos']))
                
            if poi.get('hours'):
                update_parts.append("hours = %s")
                params.append(Json(poi['hours']))
                
            if poi.get('stats'):
                update_parts.append("stats = %s")
                params.append(Json(poi['stats']))
                
            if poi.get('tips'):
                update_parts.append("tips = %s")
                params.append(Json(poi['tips']))
                
            if poi.get('amenities'):
                update_parts.append("amenities = %s")
                params.append(poi['amenities'])
                
            # Adresse formatée
            if poi.get('formatted_address'):
                update_parts.append("address = %s")
                params.append(poi['formatted_address'])
                
            # Ajouter updated_at
            update_parts.append("updated_at = %s")
            params.append(datetime.now())
            
            # Ajouter l'ID pour le WHERE
            params.append(poi['id'])
            
            # Exécuter la requête
            if update_parts:
                query = f"""
                    UPDATE locations 
                    SET {', '.join(update_parts)}
                    WHERE id = %s
                """
                cursor.execute(query, params)
                conn.commit()
                
                logger.info(f"✅ POI mis à jour: {poi['name']}")
                return True
            else:
                logger.warning(f"⚠️ Aucune mise à jour pour: {poi['name']}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur mise à jour DB: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
                
    def process_batch(self, limit: Optional[int] = None,
                     only_missing_coords: bool = False, test_mode: bool = False):
        """Traite un batch de POIs"""
        
        try:
            conn = self.connect_db()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Construire la requête
            query = "SELECT * FROM locations WHERE source_url LIKE '%tokyocheapo%'"
            params = []
            
            if only_missing_coords:
                query += " AND (latitude IS NULL OR latitude = 0 OR longitude IS NULL OR longitude = 0)"
                
            query += " ORDER BY created_at DESC"
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor.execute(query, params)
            pois = cursor.fetchall()
            
            total = len(pois)
            logger.info(f"📊 {total} POIs à traiter")
            
            if test_mode:
                logger.info("🧪 MODE TEST - Pas de mise à jour DB")
                
            # Traiter chaque POI
            for i, poi in enumerate(pois, 1):
                logger.info(f"\n[{i}/{total}] Processing...")
                self.stats['processed'] += 1
                
                # Enrichir avec Foursquare
                enriched_poi = self.enrich_poi(dict(poi))
                
                # Mettre à jour la base
                if not test_mode:
                    self.update_database(enriched_poi)
                    
                # Checkpoint tous les 50 POIs
                if i % 50 == 0:
                    self.save_checkpoint(i)
                    logger.info(f"💾 Checkpoint: {i} POIs traités")
                    
        except Exception as e:
            logger.error(f"Erreur traitement batch: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
                
        # Afficher les statistiques
        self.print_stats()
        
    def save_checkpoint(self, processed: int):
        """Sauvegarde un checkpoint pour reprise"""
        checkpoint = {
            'processed': processed,
            'stats': self.stats,
            'timestamp': datetime.now().isoformat()
        }
        with open('foursquare_checkpoint.json', 'w') as f:
            json.dump(checkpoint, f, indent=2)
            
    def load_checkpoint(self) -> Optional[Dict]:
        """Charge le dernier checkpoint"""
        try:
            if os.path.exists('foursquare_checkpoint.json'):
                with open('foursquare_checkpoint.json', 'r') as f:
                    return json.load(f)
        except:
            pass
        return None
        
    def print_stats(self):
        """Affiche les statistiques"""
        logger.info("\n" + "="*50)
        logger.info("📊 STATISTIQUES FINALES")
        logger.info("="*50)
        logger.info(f"POIs traités: {self.stats['processed']}")
        logger.info(f"Matches trouvés: {self.stats['matched']} ({self.stats['matched']*100/max(self.stats['processed'],1):.1f}%)")
        logger.info(f"Géocodés: {self.stats['geocoded']}")
        logger.info(f"Enrichis: {self.stats['enriched']}")
        logger.info(f"Échecs: {self.stats['failed']}")
        logger.info(f"Appels API: {self.stats['api_calls']}")
        logger.info(f"Coût estimé: ${self.stats['api_calls'] * 0.001:.2f}")
        logger.info("="*50)
        

def main():
    """Point d'entrée principal"""
    
    parser = argparse.ArgumentParser(description='Enrichissement Foursquare des POIs')
    # --platform removed - using source_url filter instead
    parser.add_argument('--limit', type=int, help='Nombre max de POIs à traiter')
    parser.add_argument('--only-missing-coords', action='store_true', 
                       help='Traiter seulement les POIs sans coordonnées')
    parser.add_argument('--test', action='store_true', help='Mode test (pas de mise à jour DB)')
    parser.add_argument('--resume', action='store_true', help='Reprendre depuis le dernier checkpoint')
    
    args = parser.parse_args()
    
    # Configuration Foursquare
    api_key = os.getenv('FOURSQUARE_API_KEY')
    if not api_key:
        logger.error("❌ FOURSQUARE_API_KEY non définie!")
        logger.info("👉 Créez un compte sur https://foursquare.com/developers/")
        logger.info("👉 Puis ajoutez dans .env: FOURSQUARE_API_KEY=your_key")
        sys.exit(1)
        
    config = FoursquareConfig(api_key=api_key)
    
    # Configuration DB
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'yorimichi'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', ''),
        'port': int(os.getenv('DB_PORT', 5432))
    }
    
    # Si c'est Supabase
    supabase_url = os.getenv('SUPABASE_URL')
    if supabase_url and 'supabase.co' in supabase_url:
        db_config['host'] = supabase_url.replace('https://', '').split('.')[0] + '.pooler.supabase.com'
        db_config['database'] = 'postgres'
        db_config['user'] = 'postgres.wkhtvcffqpwqxmlukfix'
        db_config['password'] = os.getenv('SUPABASE_DB_PASSWORD')
        db_config['port'] = 6543
    
    # Créer l'enrichisseur
    enricher = FoursquareEnricher(config, db_config)
    
    # Charger le checkpoint si demandé
    if args.resume:
        checkpoint = enricher.load_checkpoint()
        if checkpoint:
            enricher.stats = checkpoint['stats']
            logger.info(f"♻️ Reprise depuis le checkpoint: {checkpoint['processed']} POIs déjà traités")
    
    # Lancer le traitement
    logger.info("🚀 Démarrage de l'enrichissement Foursquare")
    logger.info(f"Source: Tokyo Cheapo (via source_url)")
    logger.info(f"Limite: {args.limit or 'Aucune'}")
    logger.info(f"Coords manquantes seulement: {args.only_missing_coords}")
    logger.info(f"Mode test: {args.test}")
    
    enricher.process_batch(
        limit=args.limit,
        only_missing_coords=args.only_missing_coords,
        test_mode=args.test
    )
    

if __name__ == "__main__":
    # Créer le dossier logs si nécessaire
    os.makedirs('logs', exist_ok=True)
    main()