#!/usr/bin/env python3
"""
Script ALL-IN-ONE pour enrichir tous les POIs avec Foursquare
Fait TOUT en une seule exécution :
1. Géocodage via Foursquare pour les coordonnées manquantes
2. Enrichissement avec métadonnées Foursquare (photos, ratings, horaires)
3. Téléchargement et stockage des images dans Supabase Storage
4. Mise à jour complète de la base de données
"""

import os
import sys
import json
import time
import logging
import argparse
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass
from io import BytesIO
import requests
from PIL import Image
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from supabase import create_client, Client

# Créer le dossier logs si nécessaire
os.makedirs('logs', exist_ok=True)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/enrich_all_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
# Essayer d'abord .env.local, sinon .env
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

@dataclass
class EnrichmentConfig:
    """Configuration pour l'enrichissement complet"""
    # Required fields (no defaults)
    foursquare_api_key: str
    supabase_url: str
    supabase_anon_key: str
    supabase_db_password: str
    db_host: str
    db_user: str
    db_password: str
    
    # Optional fields (with defaults)
    foursquare_base_url: str = "https://api.foursquare.com/v3"
    foursquare_rate_limit: int = 50  # req/sec
    image_bucket: str = "place-images"
    max_images_per_poi: int = 5
    jpeg_quality: int = 85
    db_name: str = "postgres"
    db_port: int = 6543  # Port pour le pooler Supabase


class CompleteEnricher:
    """Enrichissement complet des POIs avec Foursquare"""
    
    IMAGE_SIZES = {
        'thumb': (150, 150),
        'card': (400, 300),
        'full': (1200, 900)
    }
    
    def __init__(self, config: EnrichmentConfig):
        self.config = config
        self.setup_clients()
        self.stats = {
            'total': 0,
            'processed': 0,
            'geocoded': 0,
            'enriched': 0,
            'images_downloaded': 0,
            'images_uploaded': 0,
            'failed': 0,
            'skipped': 0,
            'api_calls': 0,
            'start_time': datetime.now()
        }
        
    def setup_clients(self):
        """Initialise tous les clients nécessaires"""
        # Foursquare session
        self.foursquare_session = requests.Session()
        self.foursquare_session.headers.update({
            'Authorization': self.config.foursquare_api_key,
            'Accept': 'application/json'
        })
        
        # Supabase client
        self.supabase = create_client(
            self.config.supabase_url,
            self.config.supabase_anon_key
        )
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
        
        # Session pour télécharger les images
        self.image_session = requests.Session()
        
    def convert_foursquare_hours(self, fsq_hours: Dict) -> Dict:
        """Convertit les horaires Foursquare vers le format standard"""
        if not fsq_hours:
            return {}
            
        converted = {}
        
        # Format Foursquare: regular: [{day: 1, open: "0900", close: "2100"}, ...]
        regular = fsq_hours.get('regular', [])
        
        days_map = {
            1: 'monday',
            2: 'tuesday', 
            3: 'wednesday',
            4: 'thursday',
            5: 'friday',
            6: 'saturday',
            7: 'sunday'
        }
        
        for schedule in regular:
            day_num = schedule.get('day')
            if day_num in days_map:
                day_name = days_map[day_num]
                open_time = schedule.get('open', '')
                close_time = schedule.get('close', '')
                
                # Convertir format HHMM vers HH:MM
                if open_time and len(open_time) == 4:
                    open_time = f"{open_time[:2]}:{open_time[2:]}"
                if close_time and len(close_time) == 4:
                    close_time = f"{close_time[:2]}:{close_time[2:]}"
                    
                converted[day_name] = {
                    'open': open_time,
                    'close': close_time
                }
                
        return converted
        
    def _ensure_bucket_exists(self):
        """Crée le bucket Supabase Storage si nécessaire"""
        try:
            buckets = self.supabase.storage.list_buckets()
            bucket_names = [b['name'] for b in buckets]
            
            if self.config.image_bucket not in bucket_names:
                # Fix: le nom du bucket doit être passé comme premier argument
                self.supabase.storage.create_bucket(
                    self.config.image_bucket  # Juste le nom, pas d'options pour l'instant
                )
                logger.info(f"✅ Bucket '{self.config.image_bucket}' créé")
            else:
                logger.info(f"✅ Bucket '{self.config.image_bucket}' existe déjà")
        except Exception as e:
            # Si le bucket existe déjà, ce n'est pas grave
            if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                logger.info(f"✅ Bucket '{self.config.image_bucket}' existe déjà")
            else:
                logger.warning(f"⚠️ Erreur vérification bucket: {e}")
                # Continuer quand même, le bucket existe peut-être déjà
            
    def connect_db(self):
        """Connexion à la base de données Supabase"""
        # Forcer IPv4 et ajouter sslmode
        return psycopg2.connect(
            host=self.config.db_host,
            database=self.config.db_name,
            user=self.config.db_user,
            password=self.config.db_password,
            port=self.config.db_port,
            sslmode='require',  # Supabase requiert SSL
            connect_timeout=10
        )
        
    def search_foursquare(self, name: str, address: Optional[str] = None,
                         lat: Optional[float] = None, lon: Optional[float] = None) -> Optional[Dict]:
        """Recherche un lieu sur Foursquare"""
        
        params = {
            'limit': 5,
            'fields': 'fsq_id,name,location,categories,rating,price,photos,hours,website,tel,verified,stats,tips,tastes,features'
        }
        
        # Stratégie de recherche
        if lat and lon and lat != 0 and lon != 0:
            params['ll'] = f"{lat},{lon}"
            params['radius'] = 500
            params['query'] = name
        elif address:
            params['near'] = f"{address}, Tokyo, Japan"
            params['query'] = name
        else:
            params['near'] = "Tokyo, Japan"
            params['query'] = name
            
        try:
            url = f"{self.config.foursquare_base_url}/places/search"
            response = self.foursquare_session.get(url, params=params, timeout=10)
            self.stats['api_calls'] += 1
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                if results:
                    return results[0]  # Meilleur match
            else:
                logger.error(f"Foursquare error {response.status_code}")
                
        except Exception as e:
            logger.error(f"Erreur recherche Foursquare: {e}")
            
        return None
        
    def get_foursquare_photos(self, fsq_id: str) -> List[str]:
        """Récupère les URLs des photos depuis Foursquare"""
        try:
            url = f"{self.config.foursquare_base_url}/places/{fsq_id}/photos"
            params = {'limit': self.config.max_images_per_poi}
            
            response = self.foursquare_session.get(url, params=params, timeout=10)
            self.stats['api_calls'] += 1
            
            if response.status_code == 200:
                photos = response.json()
                photo_urls = []
                for photo in photos:
                    photo_url = f"{photo['prefix']}original{photo['suffix']}"
                    photo_urls.append(photo_url)
                return photo_urls
        except Exception as e:
            logger.error(f"Erreur récupération photos: {e}")
            
        return []
        
    def download_and_process_image(self, url: str, poi_id: int, index: int) -> Dict[str, str]:
        """Télécharge, redimensionne et upload une image"""
        processed_urls = {}
        
        try:
            # Télécharger l'image
            response = self.image_session.get(url, timeout=10)
            if response.status_code != 200:
                return processed_urls
                
            img = Image.open(BytesIO(response.content))
            
            # Convertir en RGB si nécessaire
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    rgb_img.paste(img, mask=img.split()[3])
                else:
                    rgb_img.paste(img)
                img = rgb_img
                
            self.stats['images_downloaded'] += 1
            
            # Traiter chaque taille
            for size_name, size_dims in self.IMAGE_SIZES.items():
                # Redimensionner
                resized_img = img.copy()
                if size_dims:
                    resized_img.thumbnail(size_dims, Image.Resampling.LANCZOS)
                    
                # Optimiser
                output = BytesIO()
                resized_img.save(output, format='JPEG', quality=self.config.jpeg_quality, optimize=True)
                output.seek(0)
                
                # Générer le nom de fichier
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                filename = f"pois/{poi_id}/{size_name}_{index}_{url_hash}.jpg"
                
                # Upload vers Supabase
                try:
                    response = self.supabase.storage.from_(self.config.image_bucket).upload(
                        filename,
                        output.getvalue(),
                        {
                            'content-type': 'image/jpeg',
                            'cache-control': 'public, max-age=31536000'
                        }
                    )
                    
                    public_url = self.supabase.storage.from_(self.config.image_bucket).get_public_url(filename)
                    processed_urls[size_name] = public_url
                    self.stats['images_uploaded'] += 1
                    
                except Exception as e:
                    if 'already exists' in str(e):
                        # Récupérer l'URL existante
                        public_url = self.supabase.storage.from_(self.config.image_bucket).get_public_url(filename)
                        processed_urls[size_name] = public_url
                    else:
                        logger.error(f"Erreur upload: {e}")
                        
        except Exception as e:
            logger.error(f"Erreur traitement image: {e}")
            
        return processed_urls
        
    def enrich_poi(self, poi: Dict) -> Dict:
        """Enrichit complètement un POI"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 [{self.stats['processed']+1}/{self.stats['total']}] {poi['name']}")
        
        enriched = poi.copy()
        
        # 1. FOURSQUARE - Recherche et enrichissement
        logger.info("  📍 Recherche Foursquare...")
        fsq_place = self.search_foursquare(
            name=poi['name'],
            address=poi.get('address'),
            lat=poi.get('latitude'),
            lon=poi.get('longitude')
        )
        
        if fsq_place:
            logger.info(f"  ✅ Match trouvé: {fsq_place.get('name')}")
            
            # Géocodage si nécessaire
            location = fsq_place.get('location', {})
            if (not poi.get('latitude') or poi.get('latitude') == 0) and location.get('lat'):
                enriched['latitude'] = location['lat']
                enriched['longitude'] = location['lng']
                self.stats['geocoded'] += 1
                logger.info(f"  📍 Géocodé: {location['lat']}, {location['lng']}")
                
            # Métadonnées
            enriched['fsq_id'] = fsq_place.get('fsq_id')
            enriched['rating'] = fsq_place.get('rating')
            enriched['price_tier'] = fsq_place.get('price')
            enriched['verified'] = fsq_place.get('verified', False)
            
            # Catégories
            categories = fsq_place.get('categories', [])
            if categories:
                enriched['fsq_categories'] = [cat['name'] for cat in categories]
                # Prendre la première catégorie principale
                if categories[0]:
                    enriched['category'] = categories[0].get('name')
                
            # Adresse formatée
            if location:
                enriched['formatted_address'] = location.get('formatted_address')
                enriched['cross_street'] = location.get('cross_street')
                enriched['postal_code'] = location.get('postcode')
                
            # Contact
            enriched['phone'] = fsq_place.get('tel')
            enriched['website'] = fsq_place.get('website')
            
            # Horaires
            hours = fsq_place.get('hours')
            if hours:
                enriched['hours'] = hours
                enriched['open_now'] = hours.get('open_now')
                
            # Stats
            stats = fsq_place.get('stats', {})
            if stats:
                enriched['stats'] = stats
                
            # Features
            features = fsq_place.get('features', {})
            if features:
                enriched['amenities'] = list(features.keys())
                
            self.stats['enriched'] += 1
            
            # 2. IMAGES - Téléchargement et traitement
            if enriched['fsq_id']:
                logger.info("  📸 Récupération des photos...")
                photo_urls = self.get_foursquare_photos(enriched['fsq_id'])
                
                if photo_urls:
                    logger.info(f"  📸 {len(photo_urls)} photos trouvées")
                    all_photos = {'thumb': [], 'card': [], 'full': []}
                    
                    for i, photo_url in enumerate(photo_urls[:self.config.max_images_per_poi]):
                        logger.info(f"    Processing photo {i+1}/{len(photo_urls)}...")
                        processed = self.download_and_process_image(photo_url, poi['id'], i)
                        
                        for size_name, url in processed.items():
                            if size_name in all_photos:
                                all_photos[size_name].append(url)
                                
                    enriched['photos'] = all_photos
                    enriched['photos']['processed_at'] = datetime.now().isoformat()
                    
        else:
            logger.warning(f"  ❌ Aucun match Foursquare")
            self.stats['failed'] += 1
            
        # Rate limiting
        time.sleep(1 / self.config.foursquare_rate_limit)
        
        return enriched
        
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
                
            # Foursquare ID
            if poi.get('fsq_id'):
                update_parts.append("fsq_id = %s")
                params.append(poi['fsq_id'])
                # Marquer comme enrichi
                update_parts.append("fsq_enriched_at = %s")
                params.append(datetime.now())
                
            # Rating
            if poi.get('rating'):
                update_parts.append("rating = %s")
                params.append(poi['rating'])
                
            # Price tier
            if poi.get('price_tier'):
                update_parts.append("price_tier = %s")
                params.append(poi['price_tier'])
                
            # Verified
            if 'verified' in poi:
                update_parts.append("verified = %s")
                params.append(poi['verified'])
                
            # Phone (utiliser la colonne existante)
            if poi.get('phone'):
                update_parts.append("phone = %s")
                params.append(poi['phone'])
                
            # Website (utiliser la colonne existante)
            if poi.get('website'):
                update_parts.append("website = %s")
                params.append(poi['website'])
                
            # Photos JSON
            if poi.get('photos'):
                update_parts.append("photos = %s")
                params.append(Json(poi['photos']))
                update_parts.append("photos_processed_at = %s")
                params.append(datetime.now())
                
            # Horaires Foursquare
            if poi.get('hours'):
                # Stocker dans la nouvelle colonne hours pour Foursquare
                update_parts.append("hours = %s")
                params.append(Json(poi['hours']))
                
                # Convertir aussi vers opening_hours format standard
                converted_hours = self.convert_foursquare_hours(poi['hours'])
                if converted_hours:
                    update_parts.append("opening_hours = %s")
                    params.append(Json(converted_hours))
                
            # Stats
            if poi.get('stats'):
                update_parts.append("stats = %s")
                params.append(Json(poi['stats']))
                    
            # Amenities
            if poi.get('amenities'):
                update_parts.append("amenities = %s")
                params.append(poi['amenities'])
                # Aussi dans features pour compatibilité
                update_parts.append("features = %s")
                params.append(Json(poi['amenities']))
                
            # Catégories Foursquare
            if poi.get('fsq_categories'):
                update_parts.append("fsq_categories = %s")
                params.append(poi['fsq_categories'])
                
            # Catégorie principale
            if poi.get('category'):
                update_parts.append("category = %s")
                params.append(poi['category'])
                
            # Adresse formatée
            if poi.get('formatted_address'):
                update_parts.append("address = %s")
                params.append(poi['formatted_address'])
                
            # Updated at
            update_parts.append("updated_at = %s")
            params.append(datetime.now())
            
            # ID pour WHERE
            params.append(poi['id'])
            
            # Exécuter la mise à jour
            if update_parts:
                query = f"""
                    UPDATE locations 
                    SET {', '.join(update_parts)}
                    WHERE id = %s
                """
                cursor.execute(query, params)
                conn.commit()
                logger.info(f"  ✅ Base de données mise à jour")
                return True
            else:
                logger.warning(f"  ⚠️ Aucune mise à jour nécessaire")
                return False
                
        except Exception as e:
            logger.error(f"  ❌ Erreur mise à jour DB: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
                
    def process_all(self, limit: Optional[int] = None, only_missing_coords: bool = False,
                   test_mode: bool = False, force_update: bool = False, resume_from_id: str = None):
        """Traite tous les POIs"""
        
        logger.info("\n" + "="*60)
        logger.info("🚀 ENRICHISSEMENT COMPLET DES POIs")
        logger.info("="*60)
        
        conn = None
        cursor = None
        
        try:
            # Récupérer les POIs
            conn = self.connect_db()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Vérifier si les colonnes Foursquare existent
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='locations' AND column_name='fsq_id'
            """)
            if not cursor.fetchone():
                logger.warning("⚠️ Colonnes Foursquare manquantes! Lancez d'abord:")
                logger.warning("   python migrate_add_foursquare_columns.py")
                return
            
            # IMPORTANT: Ne PAS inclure embedding pour éviter de le régénérer (coûteux!)
            query = """
                SELECT id, name, address, latitude, longitude, description, 
                       phone, website, category, source_url, metadata, features,
                       opening_hours, fsq_id, rating, price_tier, verified,
                       photos, hours, stats, amenities, fsq_categories,
                       fsq_enriched_at, photos_processed_at
                FROM locations 
                WHERE source_url IS NOT NULL
            """
            
            # Éviter les doublons - skip les POIs déjà enrichis
            if not force_update:
                query += " AND (fsq_id IS NULL OR fsq_enriched_at IS NULL)"
            
            if only_missing_coords:
                query += " AND (latitude IS NULL OR latitude = 0)"
                
            # Reprendre après le dernier POI traité
            if resume_from_id:
                query += f" AND created_at < (SELECT created_at FROM locations WHERE id = '{resume_from_id}')"
                
            query += " ORDER BY created_at DESC"
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor.execute(query)
            pois = cursor.fetchall()
            
            self.stats['total'] = len(pois)
            logger.info(f"📊 {self.stats['total']} POIs à traiter")
            
            # Afficher plus de détails sur ce qui va être fait
            if self.stats['total'] > 0:
                sample = pois[0]
                has_coords = sum(1 for p in pois if p.get('latitude') and p['latitude'] != 0)
                has_fsq = sum(1 for p in pois if p.get('fsq_id'))
                
                logger.info(f"📍 POIs avec coordonnées: {has_coords}/{self.stats['total']} ({has_coords*100/self.stats['total']:.1f}%)")
                logger.info(f"🏷️ POIs déjà enrichis Foursquare: {has_fsq}/{self.stats['total']}")
                logger.info(f"🔄 POIs à géocoder: {self.stats['total'] - has_coords}")
                logger.info(f"💰 Coût Foursquare estimé: ${self.stats['total'] * 0.01:.2f} (gratuit dans free tier)")
                logger.info(f"⏱️ Temps estimé: {self.stats['total'] * 1.2 / 60:.0f} minutes")
            
            if test_mode:
                logger.info("🧪 MODE TEST - Pas de mise à jour DB")
                
            # Traiter chaque POI
            for poi in pois:
                self.stats['processed'] += 1
                
                # Enrichir le POI
                enriched_poi = self.enrich_poi(dict(poi))
                
                # Mettre à jour la base
                if not test_mode:
                    success = self.update_database(enriched_poi)
                    if not success:
                        logger.warning(f"⚠️ Échec mise à jour DB pour POI {poi['id']}")
                    
                # Checkpoint tous les 25 POIs
                if self.stats['processed'] % 25 == 0:
                    self.save_checkpoint(last_processed_id=str(poi['id']))
                    self.print_stats()
                    logger.info(f"⏱️ Temps écoulé: {(datetime.now() - self.stats['start_time']).total_seconds():.1f}s")
                    logger.info(f"⚡ Vitesse: {self.stats['processed']/(datetime.now() - self.stats['start_time']).total_seconds():.2f} POIs/s")
                    
                # Log de progression tous les 100 POIs
                if self.stats['processed'] % 100 == 0:
                    remaining = self.stats['total'] - self.stats['processed']
                    eta_seconds = remaining / max(self.stats['processed']/(datetime.now() - self.stats['start_time']).total_seconds(), 0.01)
                    eta_minutes = int(eta_seconds / 60)
                    logger.info(f"📈 PROGRESSION: {self.stats['processed']}/{self.stats['total']} ({self.stats['processed']*100/self.stats['total']:.1f}%)")
                    logger.info(f"⏳ Temps restant estimé: {eta_minutes} minutes")
                    
        except KeyboardInterrupt:
            logger.info("\n⚠️ Interruption utilisateur")
            # Sauvegarder le dernier ID traité
            if 'pois' in locals() and self.stats['processed'] > 0:
                last_id = pois[min(self.stats['processed']-1, len(pois)-1)]['id']
                self.save_checkpoint(last_processed_id=str(last_id))
            else:
                self.save_checkpoint()
            
        except Exception as e:
            logger.error(f"Erreur traitement: {e}")
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
                
        # Statistiques finales
        self.print_stats()
        
    def save_checkpoint(self, last_processed_id=None):
        """Sauvegarde un checkpoint pour reprise"""
        checkpoint = {
            'stats': self.stats,
            'timestamp': datetime.now().isoformat(),
            'last_processed_id': last_processed_id
        }
        with open('enrichment_checkpoint.json', 'w') as f:
            json.dump(checkpoint, f, indent=2)
        logger.info("💾 Checkpoint sauvegardé")
        
    def print_stats(self):
        """Affiche les statistiques détaillées"""
        duration = (datetime.now() - self.stats['start_time']).total_seconds()
        
        logger.info("\n" + "="*60)
        logger.info("📊 STATISTIQUES")
        logger.info("="*60)
        logger.info(f"Total POIs: {self.stats['total']}")
        logger.info(f"Traités: {self.stats['processed']} ({self.stats['processed']*100/max(self.stats['total'],1):.1f}%)")
        logger.info(f"Géocodés: {self.stats['geocoded']} nouveaux")
        logger.info(f"Enrichis Foursquare: {self.stats['enriched']}")
        logger.info(f"Images téléchargées: {self.stats['images_downloaded']}")
        logger.info(f"Images uploadées: {self.stats['images_uploaded']}")
        logger.info(f"Échecs matching: {self.stats['failed']}")
        logger.info(f"Skippés: {self.stats.get('skipped', 0)}")
        logger.info("---")
        logger.info(f"Appels API Foursquare: {self.stats['api_calls']}")
        logger.info(f"Durée totale: {duration:.1f}s ({duration/60:.1f} min)")
        logger.info(f"Vitesse moyenne: {self.stats['processed']/max(duration,1):.2f} POIs/s")
        
        # Taux de succès
        if self.stats['processed'] > 0:
            success_rate = (self.stats['enriched'] / self.stats['processed']) * 100
            logger.info(f"Taux de succès: {success_rate:.1f}%")
        
        # Estimation coût Foursquare
        cost = self.stats['api_calls'] * 0.005  # $0.005 par appel en moyenne
        logger.info(f"Coût estimé Foursquare: ${cost:.2f} (FREE TIER: $200/mois)")
        logger.info("="*60)


def main():
    """Point d'entrée principal"""
    
    parser = argparse.ArgumentParser(description='Enrichissement complet des POIs avec Foursquare')
    parser.add_argument('--limit', type=int, help='Nombre max de POIs à traiter')
    parser.add_argument('--only-missing-coords', action='store_true',
                       help='Traiter seulement les POIs sans coordonnées')
    parser.add_argument('--test', action='store_true', help='Mode test (pas de mise à jour DB)')
    parser.add_argument('--resume', action='store_true', help='Reprendre depuis le dernier checkpoint')
    parser.add_argument('--force-update', action='store_true', 
                       help='Forcer la mise à jour même des POIs déjà enrichis')
    
    args = parser.parse_args()
    
    # Vérifier les variables d'environnement
    # Support des deux formats de noms (avec ou sans NEXT_PUBLIC_)
    required_env = []
    
    # Foursquare API Key
    if not os.getenv('FOURSQUARE_API_KEY'):
        required_env.append('FOURSQUARE_API_KEY')
    
    # Supabase URL - essayer les deux formats
    if not (os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')):
        required_env.append('SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL')
    
    # Supabase Anon Key - essayer les deux formats
    if not (os.getenv('SUPABASE_ANON_KEY') or os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')):
        required_env.append('SUPABASE_ANON_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY')
    
    # Supabase DB Password - essayer les deux formats
    if not (os.getenv('SUPABASE_DB_PASSWORD') or os.getenv('SUPABASE_SERVICE_ROLE_KEY')):
        required_env.append('SUPABASE_DB_PASSWORD or SUPABASE_SERVICE_ROLE_KEY')
    
    if required_env:
        logger.error(f"❌ Variables d'environnement manquantes: {', '.join(required_env)}")
        logger.info("\n📝 Configuration requise dans .env:")
        logger.info("FOURSQUARE_API_KEY=your_key  # Depuis https://foursquare.com/developers/")
        logger.info("NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co")
        logger.info("NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key")
        logger.info("SUPABASE_SERVICE_ROLE_KEY=your_service_role_key")
        sys.exit(1)
        
    # Configuration - support des deux formats de variables
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    supabase_anon_key = os.getenv('SUPABASE_ANON_KEY') or os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    supabase_db_password = os.getenv('SUPABASE_DB_PASSWORD') or os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    project_id = supabase_url.replace('https://', '').split('.')[0]
    
    # Pour Supabase, on peut utiliser soit db. pour la connexion directe, soit pooler. pour le pooling
    # Essayons avec pooler qui est plus stable
    config = EnrichmentConfig(
        foursquare_api_key=os.getenv('FOURSQUARE_API_KEY'),
        supabase_url=supabase_url,
        supabase_anon_key=supabase_anon_key,
        supabase_db_password=supabase_db_password,
        db_host=f"aws-0-ap-northeast-1.pooler.supabase.com",  # Host pooler pour la région Tokyo
        db_user=f"postgres.{project_id}",  # Format user pour pooler
        db_password=supabase_db_password,
        db_port=6543  # Port pour le pooler
    )
    
    # Créer l'enrichisseur
    enricher = CompleteEnricher(config)
    
    # Charger le checkpoint si demandé
    resume_from_id = None
    if args.resume:
        try:
            with open('enrichment_checkpoint.json', 'r') as f:
                checkpoint = json.load(f)
                enricher.stats.update(checkpoint['stats'])
                resume_from_id = checkpoint.get('last_processed_id')
                logger.info(f"♻️ Reprise depuis checkpoint:")
                logger.info(f"   POIs déjà traités: {checkpoint['stats']['processed']}")
                logger.info(f"   Dernier ID: {resume_from_id}")
        except:
            logger.info("Pas de checkpoint trouvé, démarrage depuis le début")
            
    # Lancer le traitement
    logger.info("Configuration:")
    logger.info(f"  Limite: {args.limit or 'Aucune'}")
    logger.info(f"  Coords manquantes seulement: {args.only_missing_coords}")
    logger.info(f"  Mode test: {args.test}")
    logger.info("")
    
    enricher.process_all(
        limit=args.limit,
        only_missing_coords=args.only_missing_coords,
        test_mode=args.test,
        force_update=args.force_update,
        resume_from_id=resume_from_id
    )
    

if __name__ == "__main__":
    # Créer le dossier logs
    os.makedirs('logs', exist_ok=True)
    
    # Installer les dépendances si nécessaire
    try:
        import PIL
    except ImportError:
        logger.info("Installation de Pillow...")
        os.system("pip install Pillow")
        
    try:
        import supabase
    except ImportError:
        logger.info("Installation de supabase...")
        os.system("pip install supabase")
        
    main()