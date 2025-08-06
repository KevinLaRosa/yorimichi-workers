#!/usr/bin/env python3
"""
Script ALL-IN-ONE pour enrichir tous les POIs avec Foursquare
Utilise le SDK Supabase (plus simple et fonctionne déjà avec Tokyo Cheapo!)
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
from supabase import create_client, Client
from openai import OpenAI

# Créer le dossier logs si nécessaire
os.makedirs('logs', exist_ok=True)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/enrich_sdk_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
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
    supabase_key: str
    openai_api_key: str = None  # Optional, if provided will use GPT for better matching
    
    # Optional fields (with defaults)
    foursquare_base_url: str = "https://api.foursquare.com/v3"
    foursquare_rate_limit: int = 50  # req/sec
    search_radius: int = 1000  # 1km radius
    search_limit: int = 20  # Number of results to get from Foursquare
    image_bucket: str = "place-images"
    max_images_per_poi: int = 5
    jpeg_quality: int = 85


class CompleteEnricher:
    """Enrichissement complet des POIs avec Foursquare et SDK Supabase"""
    
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
            'no_match': 0,
            'images_downloaded': 0,
            'images_uploaded': 0,
            'failed': 0,
            'skipped': 0,
            'api_calls_foursquare': 0,
            'api_calls_openai': 0,
            'start_time': datetime.now()
        }
        
    def setup_clients(self):
        """Initialise tous les clients nécessaires"""
        # Foursquare session
        self.foursquare_session = requests.Session()
        self.foursquare_session.headers.update({
            'Authorization': f'Bearer {self.config.foursquare_api_key}',  # Bearer token pour Service API Keys
            'Accept': 'application/json'
        })
        
        # Supabase client - comme dans Tokyo Cheapo!
        self.supabase: Client = create_client(
            self.config.supabase_url,
            self.config.supabase_key
        )
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
        
        # Session pour télécharger les images
        self.image_session = requests.Session()
        
        # OpenAI client (si API key fournie)
        if self.config.openai_api_key:
            self.openai_client = OpenAI(api_key=self.config.openai_api_key)
            logger.info("✅ GPT-4o-mini activé pour un meilleur matching")
        else:
            self.openai_client = None
            logger.warning("⚠️ Pas d'API OpenAI - matching basique (premier résultat)")
        
    def _ensure_bucket_exists(self):
        """Crée le bucket Supabase Storage si nécessaire"""
        try:
            buckets = self.supabase.storage.list_buckets()
            bucket_names = [b['name'] for b in buckets]
            
            if self.config.image_bucket not in bucket_names:
                logger.info(f"📦 Création du bucket '{self.config.image_bucket}'...")
                # Créer le bucket
                self.supabase.storage.create_bucket(self.config.image_bucket)
                logger.info(f"✅ Bucket '{self.config.image_bucket}' créé")
            else:
                logger.info(f"✅ Bucket '{self.config.image_bucket}' existe déjà")
        except Exception as e:
            # Si le bucket existe déjà, ce n'est pas grave
            logger.warning(f"⚠️ Erreur vérification bucket: {e}")
            # Continuer quand même
            
    def search_foursquare_places(self, name: str, address: Optional[str] = None,
                                lat: Optional[float] = None, lon: Optional[float] = None) -> List[Dict]:
        """Recherche des lieux sur Foursquare avec paramètres améliorés"""
        
        params = {
            'query': name,
            'limit': self.config.search_limit,  # 20 candidats
            'fields': 'fsq_id,name,location,categories,rating,price,photos,hours,website,tel,verified,distance,stats,tips,tastes,features'
        }
        
        # Stratégie de recherche améliorée
        if lat and lon and lat != 0 and lon != 0:
            params['ll'] = f"{lat},{lon}"
            params['radius'] = self.config.search_radius  # 1000m
        elif address:
            params['near'] = f"{address}, Tokyo, Japan"
        else:
            params['near'] = "Tokyo, Japan"
            
        try:
            url = f"{self.config.foursquare_base_url}/places/search"
            response = self.foursquare_session.get(url, params=params, timeout=10)
            self.stats['api_calls_foursquare'] += 1
            
            if response.status_code == 200:
                data = response.json()
                return data.get('results', [])
            else:
                logger.error(f"Foursquare error {response.status_code}")
                
        except Exception as e:
            logger.error(f"Erreur recherche Foursquare: {e}")
            
        return []
    
    def select_best_match_with_gpt(self, poi_name: str, poi_address: Optional[str],
                                   candidates: List[Dict]) -> Optional[Dict]:
        """Utilise GPT-4o-mini pour sélectionner le meilleur match"""
        
        if not self.openai_client:
            # Pas de GPT, retourner le premier candidat
            return candidates[0] if candidates else None
        
        if not candidates:
            return None
            
        # Si un seul candidat, le retourner
        if len(candidates) == 1:
            return candidates[0]
            
        try:
            # Préparer le contexte pour GPT
            candidates_info = []
            for i, candidate in enumerate(candidates):
                location = candidate.get('location', {})
                categories = ', '.join([cat['name'] for cat in candidate.get('categories', [])])
                distance = candidate.get('distance', 'N/A')
                
                candidate_info = {
                    'index': i,
                    'name': candidate.get('name'),
                    'address': location.get('formatted_address', location.get('address', 'N/A')),
                    'categories': categories or 'N/A',
                    'distance': f"{distance}m" if distance != 'N/A' else 'N/A',
                    'verified': candidate.get('verified', False)
                }
                candidates_info.append(candidate_info)
                
            # Créer le prompt pour GPT
            prompt = f"""Tu es un assistant spécialisé dans le matching de lieux à Tokyo.
            
POI à matcher:
- Nom: {poi_name}
- Adresse: {poi_address or 'Non spécifiée'}

Candidats Foursquare:
{json.dumps(candidates_info, indent=2, ensure_ascii=False)}

Sélectionne le candidat qui correspond LE MIEUX au POI. Priorise:
1. La correspondance exacte ou très proche du nom
2. La proximité géographique (distance)
3. La catégorie appropriée
4. Le statut vérifié

Réponds UNIQUEMENT avec l'index du meilleur candidat (0 à {len(candidates)-1}).
Si aucun candidat ne correspond vraiment, réponds -1.

Réponse (index uniquement):"""

            # Appeler GPT-4o-mini
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Tu es un expert en géolocalisation et matching de lieux à Tokyo."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Basse température pour des réponses cohérentes
                max_tokens=10
            )
            self.stats['api_calls_openai'] += 1
            
            # Parser la réponse
            answer = response.choices[0].message.content.strip()
            
            try:
                index = int(answer)
                if -1 <= index < len(candidates):
                    if index == -1:
                        logger.info(f"  ❌ GPT: Aucun match satisfaisant")
                        return None
                    else:
                        selected = candidates[index]
                        logger.info(f"  ✅ GPT a sélectionné: {selected.get('name')} (index {index})")
                        return selected
            except ValueError:
                logger.error(f"  ❌ GPT réponse invalide: {answer}")
                
        except Exception as e:
            logger.error(f"Erreur GPT: {e}")
            
        # En cas d'erreur, retourner le premier candidat
        return candidates[0] if candidates else None
        
    def get_foursquare_photos(self, fsq_id: str) -> List[str]:
        """Récupère les URLs des photos depuis Foursquare"""
        try:
            url = f"{self.config.foursquare_base_url}/places/{fsq_id}/photos"
            params = {'limit': self.config.max_images_per_poi}
            
            response = self.foursquare_session.get(url, params=params, timeout=10)
            self.stats['api_calls_foursquare'] += 1
            
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
        
    def download_and_process_image(self, url: str, poi_id: str, index: int) -> Dict[str, str]:
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
        """Enrichit complètement un POI avec GPT matching si disponible"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 [{self.stats['processed']+1}/{self.stats['total']}] {poi['name']}")
        
        enriched = {}
        
        # 1. FOURSQUARE - Recherche et enrichissement
        logger.info("  📍 Recherche Foursquare...")
        candidates = self.search_foursquare_places(
            name=poi['name'],
            address=poi.get('address'),
            lat=poi.get('latitude'),
            lon=poi.get('longitude')
        )
        
        if not candidates:
            logger.warning(f"  ❌ Aucun candidat Foursquare trouvé")
            self.stats['no_match'] += 1
            # Marquer comme no_match
            enriched['enrichment_status'] = 'no_match'
            enriched['enrichment_error'] = 'Aucun candidat Foursquare trouvé'
            enriched['enrichment_attempts'] = (poi.get('enrichment_attempts', 0) or 0) + 1
            enriched['last_enrichment_attempt'] = datetime.now().isoformat()
            return enriched
        
        logger.info(f"  📊 {len(candidates)} candidats trouvés")
        
        # Sélectionner le meilleur match (avec GPT si disponible)
        if self.openai_client:
            logger.info("  🤖 Analyse avec GPT-4o-mini...")
        fsq_place = self.select_best_match_with_gpt(
            poi_name=poi['name'],
            poi_address=poi.get('address'),
            candidates=candidates
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
                # formatted_address n'existe pas dans la base de données
                # enriched['formatted_address'] = location.get('formatted_address')
                if location.get('formatted_address'):
                    enriched['address'] = location.get('formatted_address')
                # cross_street n'existe pas dans la base de données
                # enriched['cross_street'] = location.get('cross_street')
                # postal_code n'existe pas dans la base de données
                # enriched['postal_code'] = location.get('postcode')
                
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
                enriched['features'] = features
                
            # Timestamps et statut
            enriched['fsq_enriched_at'] = datetime.now().isoformat()
            enriched['updated_at'] = datetime.now().isoformat()
            enriched['enrichment_status'] = 'enriched'
            enriched['enrichment_error'] = None
            enriched['enrichment_attempts'] = (poi.get('enrichment_attempts', 0) or 0) + 1
            enriched['last_enrichment_attempt'] = datetime.now().isoformat()
                
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
                    enriched['photos_processed_at'] = datetime.now().isoformat()
                    
        else:
            logger.warning(f"  ❌ Aucun match Foursquare acceptable")
            self.stats['no_match'] += 1
            # GPT n'a trouvé aucun bon match
            enriched['enrichment_status'] = 'no_match'
            enriched['enrichment_error'] = 'GPT: Aucun match satisfaisant'
            enriched['enrichment_attempts'] = (poi.get('enrichment_attempts', 0) or 0) + 1
            enriched['last_enrichment_attempt'] = datetime.now().isoformat()
            
        # Rate limiting
        time.sleep(1 / self.config.foursquare_rate_limit)
        
        return enriched
        
    def process_all(self, limit: Optional[int] = None, only_missing_coords: bool = False,
                   test_mode: bool = False, force_update: bool = False, resume_from_id: str = None):
        """Traite tous les POIs avec le SDK Supabase"""
        
        logger.info("\n" + "="*60)
        logger.info("🚀 ENRICHISSEMENT COMPLET DES POIs (SDK Supabase)")
        logger.info("="*60)
        
        try:
            # Construire la requête
            query = self.supabase.table('locations').select('*')
            
            # Filtres
            if not force_update:
                # Priorité aux POIs jamais traités (pending)
                query = query.eq('enrichment_status', 'pending')
            
            if only_missing_coords:
                query = query.or_('latitude.is.null,latitude.eq.0')
                
            # Limite
            if limit:
                query = query.limit(limit)
                
            # Exécuter la requête
            result = query.execute()
            pois = result.data
            
            self.stats['total'] = len(pois)
            logger.info(f"📊 {self.stats['total']} POIs à traiter")
            
            # Afficher plus de détails
            if self.stats['total'] > 0:
                has_coords = sum(1 for p in pois if p.get('latitude') and p['latitude'] != 0)
                has_fsq = sum(1 for p in pois if p.get('fsq_id'))
                
                logger.info(f"📍 POIs avec coordonnées: {has_coords}/{self.stats['total']} ({has_coords*100/self.stats['total']:.1f}%)")
                logger.info(f"🏷️ POIs déjà enrichis Foursquare: {has_fsq}/{self.stats['total']}")
                logger.info(f"🔄 POIs à géocoder: {self.stats['total'] - has_coords}")
                logger.info(f"💰 Coût Foursquare estimé: $0 (FREE TIER)")
                logger.info(f"⏱️ Temps estimé: {self.stats['total'] * 1.2 / 60:.0f} minutes")
            
            if test_mode:
                logger.info("🧪 MODE TEST - Pas de mise à jour DB")
                
            # Traiter chaque POI
            for poi in pois:
                self.stats['processed'] += 1
                
                # Enrichir le POI
                enriched_data = self.enrich_poi(poi)
                
                # Mettre à jour la base avec SDK Supabase
                if not test_mode and enriched_data:
                    try:
                        # Utiliser update() comme dans Tokyo Cheapo
                        self.supabase.table('locations') \
                            .update(enriched_data) \
                            .eq('id', poi['id']) \
                            .execute()
                        logger.info(f"  ✅ Base de données mise à jour")
                    except Exception as e:
                        logger.error(f"  ❌ Erreur mise à jour DB: {e}")
                        
                # Checkpoint tous les 25 POIs
                if self.stats['processed'] % 25 == 0:
                    self.save_checkpoint(last_processed_id=str(poi['id']))
                    self.print_stats()
                    
                # Log de progression tous les 100 POIs
                if self.stats['processed'] % 100 == 0:
                    remaining = self.stats['total'] - self.stats['processed']
                    eta_seconds = remaining / max(self.stats['processed']/(datetime.now() - self.stats['start_time']).total_seconds(), 0.01)
                    eta_minutes = int(eta_seconds / 60)
                    logger.info(f"📈 PROGRESSION: {self.stats['processed']}/{self.stats['total']} ({self.stats['processed']*100/self.stats['total']:.1f}%)")
                    logger.info(f"⏳ Temps restant estimé: {eta_minutes} minutes")
                    
        except KeyboardInterrupt:
            logger.info("\n⚠️ Interruption utilisateur")
            self.save_checkpoint()
            
        except Exception as e:
            logger.error(f"Erreur traitement: {e}")
                
        # Statistiques finales
        self.print_stats()
        
    def save_checkpoint(self, last_processed_id=None):
        """Sauvegarde un checkpoint pour reprise"""
        # Convertir start_time en string pour JSON
        stats_copy = self.stats.copy()
        stats_copy['start_time'] = stats_copy['start_time'].isoformat()
        
        checkpoint = {
            'stats': stats_copy,
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
        logger.info(f"Aucun match trouvé: {self.stats['no_match']}")
        logger.info(f"Images téléchargées: {self.stats['images_downloaded']}")
        logger.info(f"Images uploadées: {self.stats['images_uploaded']}")
        logger.info(f"Échecs techniques: {self.stats['failed']}")
        logger.info(f"Skippés: {self.stats.get('skipped', 0)}")
        logger.info("---")
        logger.info(f"Appels API Foursquare: {self.stats['api_calls_foursquare']}")
        logger.info(f"Appels API OpenAI: {self.stats['api_calls_openai']}")
        logger.info(f"Durée totale: {duration:.1f}s ({duration/60:.1f} min)")
        logger.info(f"Vitesse moyenne: {self.stats['processed']/max(duration,1):.2f} POIs/s")
        
        # Taux de succès
        if self.stats['processed'] > 0:
            success_rate = (self.stats['enriched'] / self.stats['processed']) * 100
            logger.info(f"Taux de succès: {success_rate:.1f}%")
        
        # Estimation coût Foursquare
        logger.info(f"Coût estimé Foursquare: $0.00 (FREE TIER: $200/mois)")
        logger.info("="*60)


def main():
    """Point d'entrée principal"""
    
    parser = argparse.ArgumentParser(description='Enrichissement POIs avec SDK Supabase')
    parser.add_argument('--limit', type=int, help='Nombre max de POIs à traiter')
    parser.add_argument('--only-missing-coords', action='store_true',
                       help='Traiter seulement les POIs sans coordonnées')
    parser.add_argument('--test', action='store_true', help='Mode test (pas de mise à jour DB)')
    parser.add_argument('--resume', action='store_true', help='Reprendre depuis le dernier checkpoint')
    parser.add_argument('--force-update', action='store_true', 
                       help='Forcer la mise à jour même des POIs déjà enrichis')
    
    args = parser.parse_args()
    
    # Vérifier les variables d'environnement
    required_vars = []
    
    # Foursquare API Key
    if not os.getenv('FOURSQUARE_API_KEY'):
        required_vars.append('FOURSQUARE_API_KEY')
    
    # Supabase URL - essayer les deux formats
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    if not supabase_url:
        required_vars.append('SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL')
    
    # Supabase Key - essayer service role en priorité
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY') or os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    if not supabase_key:
        required_vars.append('SUPABASE_SERVICE_ROLE_KEY')
    
    if required_vars:
        logger.error(f"❌ Variables d'environnement manquantes: {', '.join(required_vars)}")
        logger.info("\n📝 Configuration requise dans .env.local:")
        logger.info("FOURSQUARE_API_KEY=your_key")
        logger.info("NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co")
        logger.info("SUPABASE_SERVICE_ROLE_KEY=your_service_role_key")
        sys.exit(1)
    
    # OpenAI API Key (optionnel mais recommandé)
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        logger.warning("⚠️ OPENAI_API_KEY non trouvée - matching basique sans GPT")
        logger.info("   Pour un meilleur matching, ajoutez OPENAI_API_KEY dans .env.local")
    else:
        logger.info("✅ OpenAI API configurée - matching intelligent avec GPT-4o-mini")
        
    # Configuration
    config = EnrichmentConfig(
        foursquare_api_key=os.getenv('FOURSQUARE_API_KEY'),
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        openai_api_key=openai_key  # Peut être None, c'est OK
    )
    
    # Créer l'enrichisseur
    enricher = CompleteEnricher(config)
    
    # Charger le checkpoint si demandé
    resume_from_id = None
    if args.resume:
        try:
            with open('enrichment_checkpoint.json', 'r') as f:
                checkpoint = json.load(f)
                # Reconvertir start_time en datetime
                stats = checkpoint['stats']
                stats['start_time'] = datetime.fromisoformat(stats['start_time'])
                enricher.stats.update(stats)
                resume_from_id = checkpoint.get('last_processed_id')
                logger.info(f"♻️ Reprise depuis checkpoint:")
                logger.info(f"   POIs déjà traités: {checkpoint['stats']['processed']}")
                logger.info(f"   Dernier ID: {resume_from_id}")
        except:
            logger.info("Pas de checkpoint trouvé, démarrage depuis le début")
            
    # Lancer le traitement
    logger.info("Configuration:")
    logger.info(f"  SDK: Supabase (comme Tokyo Cheapo!)")
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