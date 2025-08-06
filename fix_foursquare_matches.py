#!/usr/bin/env python3
"""
Script pour corriger les matchs Foursquare incorrects
Utilise GPT-4o-mini pour sélectionner le meilleur match parmi les résultats
"""

import os
import sys
import json
import time
import logging
import argparse
import hashlib
from typing import Dict, List, Optional, Tuple
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
        logging.FileHandler(f'logs/fix_foursquare_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
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
class FixerConfig:
    """Configuration pour la correction des matchs"""
    foursquare_api_key: str
    supabase_url: str
    supabase_key: str
    openai_api_key: str
    
    foursquare_base_url: str = "https://api.foursquare.com/v3"
    search_radius: int = 1000  # 1km radius
    search_limit: int = 20  # Number of results to get from Foursquare (increased for dense Tokyo areas)
    foursquare_rate_limit: int = 50  # req/sec
    image_bucket: str = "place-images"
    max_images_per_poi: int = 5
    jpeg_quality: int = 85


class FoursquareMatchFixer:
    """Corrige les matchs Foursquare incorrects avec GPT-4o-mini"""
    
    IMAGE_SIZES = {
        'thumb': (150, 150),
        'card': (400, 300),
        'full': (1200, 900)
    }
    
    def __init__(self, config: FixerConfig):
        self.config = config
        self.setup_clients()
        self.stats = {
            'total': 0,
            'processed': 0,
            'fixed': 0,
            'unchanged': 0,
            'failed': 0,
            'images_deleted': 0,
            'images_downloaded': 0,
            'images_uploaded': 0,
            'api_calls_foursquare': 0,
            'api_calls_openai': 0,
            'start_time': datetime.now()
        }
        
    def setup_clients(self):
        """Initialise tous les clients nécessaires"""
        # Foursquare session
        self.foursquare_session = requests.Session()
        self.foursquare_session.headers.update({
            'Authorization': f'Bearer {self.config.foursquare_api_key}',
            'Accept': 'application/json'
        })
        
        # Supabase client
        self.supabase: Client = create_client(
            self.config.supabase_url,
            self.config.supabase_key
        )
        
        # Session pour télécharger les images
        self.image_session = requests.Session()
        
        # OpenAI client
        self.openai_client = OpenAI(api_key=self.config.openai_api_key)
        
    def search_foursquare_places(self, name: str, lat: Optional[float] = None, 
                                lon: Optional[float] = None) -> List[Dict]:
        """Recherche des lieux sur Foursquare avec paramètres précis"""
        
        params = {
            'query': name,
            'limit': self.config.search_limit,
            'fields': 'fsq_id,name,location,categories,rating,price,verified,distance'
        }
        
        # Si on a des coordonnées, les utiliser pour la recherche
        if lat and lon and lat != 0 and lon != 0:
            params['ll'] = f"{lat},{lon}"
            params['radius'] = self.config.search_radius
        else:
            # Sinon, chercher dans Tokyo
            params['near'] = "Tokyo, Japan"
            
        try:
            url = f"{self.config.foursquare_base_url}/places/search"
            response = self.foursquare_session.get(url, params=params, timeout=10)
            self.stats['api_calls_foursquare'] += 1
            
            if response.status_code == 200:
                data = response.json()
                return data.get('results', [])
            else:
                logger.error(f"Foursquare error {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"Erreur recherche Foursquare: {e}")
            
        return []
        
    def select_best_match_with_gpt(self, poi_name: str, poi_address: Optional[str],
                                   candidates: List[Dict]) -> Optional[Dict]:
        """Utilise GPT-4o-mini pour sélectionner le meilleur match"""
        
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
        
    def delete_existing_images(self, poi_id: str):
        """Supprime toutes les images existantes d'un POI"""
        try:
            # Lister tous les fichiers dans le dossier du POI
            folder_path = f"pois/{poi_id}"
            files = self.supabase.storage.from_(self.config.image_bucket).list(folder_path)
            
            if files:
                logger.info(f"  🗑️ Suppression de {len(files)} images existantes...")
                for file in files:
                    file_path = f"{folder_path}/{file['name']}"
                    try:
                        self.supabase.storage.from_(self.config.image_bucket).remove([file_path])
                        self.stats['images_deleted'] += 1
                    except Exception as e:
                        logger.warning(f"    Erreur suppression {file['name']}: {e}")
                        
        except Exception as e:
            logger.warning(f"  ⚠️ Erreur listage images existantes: {e}")
            
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
                    logger.error(f"Erreur upload {size_name}: {e}")
                    
        except Exception as e:
            logger.error(f"Erreur traitement image: {e}")
            
        return processed_urls
        
    def update_poi_images(self, poi_id: str, fsq_id: str) -> Optional[Dict]:
        """Met à jour les images d'un POI"""
        try:
            # Supprimer les anciennes images
            self.delete_existing_images(poi_id)
            
            # Récupérer les nouvelles photos
            logger.info("  📸 Récupération des nouvelles photos...")
            photo_urls = self.get_foursquare_photos(fsq_id)
            
            if not photo_urls:
                logger.info("  ℹ️ Aucune photo disponible")
                return {'photos': {'thumb': [], 'card': [], 'full': []}}
                
            logger.info(f"  📸 {len(photo_urls)} photos trouvées")
            all_photos = {'thumb': [], 'card': [], 'full': []}
            
            for i, photo_url in enumerate(photo_urls[:self.config.max_images_per_poi]):
                logger.info(f"    Processing photo {i+1}/{len(photo_urls)}...")
                processed = self.download_and_process_image(photo_url, poi_id, i)
                
                for size_name, url in processed.items():
                    if size_name in all_photos:
                        all_photos[size_name].append(url)
                        
            return {
                'photos': all_photos,
                'photos_processed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur mise à jour images: {e}")
            return None
        
    def fix_poi_match(self, poi: Dict) -> Optional[Dict]:
        """Corrige le match Foursquare d'un POI"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 [{self.stats['processed']+1}/{self.stats['total']}] {poi['name']}")
        logger.info(f"  FSQ actuel: {poi.get('fsq_id')}")
        
        # Rechercher des candidats sur Foursquare
        logger.info("  📍 Recherche de meilleurs matchs...")
        candidates = self.search_foursquare_places(
            name=poi['name'],
            lat=poi.get('latitude'),
            lon=poi.get('longitude')
        )
        
        if not candidates:
            logger.warning(f"  ❌ Aucun candidat trouvé")
            self.stats['failed'] += 1
            return None
            
        logger.info(f"  📊 {len(candidates)} candidats trouvés")
        
        # Sélectionner le meilleur match avec GPT
        logger.info("  🤖 Analyse avec GPT-4o-mini...")
        best_match = self.select_best_match_with_gpt(
            poi_name=poi['name'],
            poi_address=poi.get('address'),
            candidates=candidates
        )
        
        if not best_match:
            self.stats['failed'] += 1
            return None
            
        # Vérifier si c'est un nouveau match
        new_fsq_id = best_match.get('fsq_id')
        if new_fsq_id == poi.get('fsq_id'):
            logger.info(f"  ✅ Match correct confirmé")
            self.stats['unchanged'] += 1
            return None
            
        # Préparer les données mises à jour
        logger.info(f"  🔄 Nouveau match: {best_match.get('name')} ({new_fsq_id})")
        
        updated_data = {
            'fsq_id': new_fsq_id,
            'rating': best_match.get('rating'),
            'price_tier': best_match.get('price'),
            'verified': best_match.get('verified', False),
            'updated_at': datetime.now().isoformat()
        }
        
        # Mettre à jour les catégories
        categories = best_match.get('categories', [])
        if categories:
            updated_data['fsq_categories'] = [cat['name'] for cat in categories]
            if categories[0]:
                updated_data['category'] = categories[0].get('name')
                
        # Mettre à jour l'adresse si meilleure
        location = best_match.get('location', {})
        if location.get('formatted_address'):
            updated_data['address'] = location['formatted_address']
            
        # Mettre à jour les coordonnées si manquantes
        if (not poi.get('latitude') or poi.get('latitude') == 0) and location.get('lat'):
            updated_data['latitude'] = location['lat']
            updated_data['longitude'] = location['lng']
            logger.info(f"  📍 Coordonnées ajoutées: {location['lat']}, {location['lng']}")
            
        # Mettre à jour les images
        logger.info("  🖼️ Mise à jour des images...")
        image_data = self.update_poi_images(poi['id'], new_fsq_id)
        if image_data:
            updated_data.update(image_data)
            
        self.stats['fixed'] += 1
        return updated_data
        
    def process_all(self, limit: Optional[int] = None, test_mode: bool = False):
        """Traite tous les POIs avec fsq_id pour vérifier/corriger les matchs"""
        
        logger.info("\n" + "="*60)
        logger.info("🔧 CORRECTION DES MATCHS FOURSQUARE")
        logger.info("="*60)
        
        try:
            # Récupérer les POIs avec fsq_id
            query = self.supabase.table('locations').select('*').not_.is_('fsq_id', 'null')
            
            if limit:
                query = query.limit(limit)
                
            result = query.execute()
            pois = result.data
            
            self.stats['total'] = len(pois)
            logger.info(f"📊 {self.stats['total']} POIs avec FSQ ID à vérifier")
            
            if test_mode:
                logger.info("🧪 MODE TEST - Pas de mise à jour DB")
                
            # Traiter chaque POI
            for poi in pois:
                self.stats['processed'] += 1
                
                # Corriger le match
                updated_data = self.fix_poi_match(poi)
                
                # Mettre à jour la base si nécessaire
                if updated_data and not test_mode:
                    try:
                        self.supabase.table('locations') \
                            .update(updated_data) \
                            .eq('id', poi['id']) \
                            .execute()
                        logger.info(f"  ✅ Base de données mise à jour")
                    except Exception as e:
                        logger.error(f"  ❌ Erreur mise à jour DB: {e}")
                        
                # Rate limiting
                time.sleep(1 / self.config.foursquare_rate_limit)
                
        except KeyboardInterrupt:
            logger.info("\n⚠️ Interruption utilisateur")
            
        except Exception as e:
            logger.error(f"Erreur traitement: {e}")
            
        # Statistiques finales
        self.print_stats()
        
    def print_stats(self):
        """Affiche les statistiques"""
        duration = (datetime.now() - self.stats['start_time']).total_seconds()
        
        logger.info("\n" + "="*60)
        logger.info("📊 STATISTIQUES")
        logger.info("="*60)
        logger.info(f"Total POIs: {self.stats['total']}")
        logger.info(f"Traités: {self.stats['processed']}")
        logger.info(f"Corrigés: {self.stats['fixed']}")
        logger.info(f"Inchangés: {self.stats['unchanged']}")
        logger.info(f"Échecs: {self.stats['failed']}")
        logger.info("---")
        logger.info(f"Images supprimées: {self.stats['images_deleted']}")
        logger.info(f"Images téléchargées: {self.stats['images_downloaded']}")
        logger.info(f"Images uploadées: {self.stats['images_uploaded']}")
        logger.info("---")
        logger.info(f"Appels API Foursquare: {self.stats['api_calls_foursquare']}")
        logger.info(f"Appels API OpenAI: {self.stats['api_calls_openai']}")
        logger.info(f"Durée: {duration:.1f}s ({duration/60:.1f} min)")
        
        if self.stats['processed'] > 0:
            fix_rate = (self.stats['fixed'] / self.stats['processed']) * 100
            logger.info(f"Taux de correction: {fix_rate:.1f}%")


def main():
    """Point d'entrée principal"""
    
    parser = argparse.ArgumentParser(description='Correction des matchs Foursquare avec GPT')
    parser.add_argument('--limit', type=int, help='Nombre max de POIs à traiter')
    parser.add_argument('--test', action='store_true', help='Mode test (pas de mise à jour DB)')
    
    args = parser.parse_args()
    
    # Vérifier les variables d'environnement
    required_vars = []
    
    # Foursquare API Key
    if not os.getenv('FOURSQUARE_API_KEY'):
        required_vars.append('FOURSQUARE_API_KEY')
        
    # OpenAI API Key
    if not os.getenv('OPENAI_API_KEY'):
        required_vars.append('OPENAI_API_KEY')
    
    # Supabase
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    if not supabase_url:
        required_vars.append('SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL')
    
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
    if not supabase_key:
        required_vars.append('SUPABASE_SERVICE_ROLE_KEY')
    
    if required_vars:
        logger.error(f"❌ Variables d'environnement manquantes: {', '.join(required_vars)}")
        logger.info("\n📝 Configuration requise dans .env.local:")
        logger.info("FOURSQUARE_API_KEY=your_key")
        logger.info("OPENAI_API_KEY=your_openai_key")
        logger.info("NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co")
        logger.info("SUPABASE_SERVICE_ROLE_KEY=your_service_role_key")
        sys.exit(1)
        
    # Configuration
    config = FixerConfig(
        foursquare_api_key=os.getenv('FOURSQUARE_API_KEY'),
        openai_api_key=os.getenv('OPENAI_API_KEY'),
        supabase_url=supabase_url,
        supabase_key=supabase_key
    )
    
    # Créer le fixer
    fixer = FoursquareMatchFixer(config)
    
    # Lancer le traitement
    logger.info("Configuration:")
    logger.info(f"  Limite: {args.limit or 'Aucune'}")
    logger.info(f"  Mode test: {args.test}")
    logger.info(f"  Radius: {config.search_radius}m")
    logger.info(f"  Candidats max: {config.search_limit}")
    logger.info("")
    
    fixer.process_all(
        limit=args.limit,
        test_mode=args.test
    )


if __name__ == "__main__":
    main()