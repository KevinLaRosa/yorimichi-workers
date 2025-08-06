#!/usr/bin/env python3
"""
Script pour télécharger les images depuis Foursquare et les stocker dans Supabase Storage
- Télécharge les images depuis les URLs Foursquare
- Redimensionne en plusieurs tailles (thumb, card, full)
- Upload vers Supabase Storage
- Met à jour les URLs dans la base de données
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
from io import BytesIO
import requests
from PIL import Image
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from supabase import create_client, Client

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/image_download_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

class ImageProcessor:
    """Traitement et upload des images vers Supabase Storage"""
    
    # Configurations des tailles d'images
    IMAGE_SIZES = {
        'thumb': (150, 150),      # Thumbnail pour listes
        'card': (400, 300),       # Pour cartes
        'full': (1200, 900),      # Taille maximale
        'original': None          # Original sans redimensionnement
    }
    
    # Configuration qualité et format
    JPEG_QUALITY = 85
    WEBP_QUALITY = 80
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB max
    
    def __init__(self, supabase_client: Client, bucket_name: str = 'place-images'):
        self.supabase = supabase_client
        self.bucket_name = bucket_name
        self.session = requests.Session()
        self.stats = {
            'downloaded': 0,
            'uploaded': 0,
            'failed': 0,
            'skipped': 0,
            'total_size': 0
        }
        
        # Créer le bucket si nécessaire
        self._ensure_bucket_exists()
        
    def _ensure_bucket_exists(self):
        """Crée le bucket Supabase Storage si nécessaire"""
        try:
            buckets = self.supabase.storage.list_buckets()
            bucket_names = [b['name'] for b in buckets]
            
            if self.bucket_name not in bucket_names:
                # Créer le bucket avec politique publique pour lecture
                self.supabase.storage.create_bucket(
                    self.bucket_name,
                    {
                        'public': True,  # Lecture publique
                        'file_size_limit': self.MAX_FILE_SIZE,
                        'allowed_mime_types': ['image/jpeg', 'image/png', 'image/webp']
                    }
                )
                logger.info(f"✅ Bucket '{self.bucket_name}' créé")
            else:
                logger.info(f"✅ Bucket '{self.bucket_name}' existe déjà")
                
        except Exception as e:
            logger.error(f"Erreur création bucket: {e}")
            
    def download_image(self, url: str) -> Optional[Image.Image]:
        """Télécharge une image depuis une URL"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                # Convertir en RGB si nécessaire (pour éviter les problèmes avec PNG transparents)
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        rgb_img.paste(img, mask=img.split()[3])
                    else:
                        rgb_img.paste(img)
                    img = rgb_img
                self.stats['downloaded'] += 1
                return img
            else:
                logger.warning(f"Erreur téléchargement {response.status_code}: {url}")
                return None
        except Exception as e:
            logger.error(f"Erreur téléchargement image: {e}")
            self.stats['failed'] += 1
            return None
            
    def resize_image(self, img: Image.Image, size: Optional[Tuple[int, int]]) -> Image.Image:
        """Redimensionne une image en gardant le ratio"""
        if size is None:
            return img
            
        # Calculer le nouveau ratio
        img.thumbnail(size, Image.Resampling.LANCZOS)
        return img
        
    def optimize_image(self, img: Image.Image, format: str = 'JPEG') -> BytesIO:
        """Optimise une image pour le web"""
        output = BytesIO()
        
        if format == 'WEBP':
            img.save(output, format='WEBP', quality=self.WEBP_QUALITY, optimize=True)
        else:
            img.save(output, format='JPEG', quality=self.JPEG_QUALITY, optimize=True)
            
        output.seek(0)
        return output
        
    def generate_filename(self, poi_id: int, url: str, size: str) -> str:
        """Génère un nom de fichier unique"""
        # Hash de l'URL pour éviter les doublons
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # Format: platform/poi_id/size_hash.jpg
        # Ex: tokyo_cheapo/123/thumb_abc123.jpg
        return f"tokyo_cheapo/{poi_id}/{size}_{url_hash}.jpg"
        
    def upload_to_supabase(self, image_data: BytesIO, filepath: str) -> Optional[str]:
        """Upload une image vers Supabase Storage"""
        try:
            # Upload vers Supabase
            response = self.supabase.storage.from_(self.bucket_name).upload(
                filepath,
                image_data.getvalue(),
                {
                    'content-type': 'image/jpeg',
                    'cache-control': 'public, max-age=31536000'  # Cache 1 an
                }
            )
            
            # Récupérer l'URL publique
            public_url = self.supabase.storage.from_(self.bucket_name).get_public_url(filepath)
            
            self.stats['uploaded'] += 1
            self.stats['total_size'] += len(image_data.getvalue())
            
            logger.info(f"✅ Uploadé: {filepath}")
            return public_url
            
        except Exception as e:
            # Si le fichier existe déjà, récupérer son URL
            if 'already exists' in str(e):
                public_url = self.supabase.storage.from_(self.bucket_name).get_public_url(filepath)
                self.stats['skipped'] += 1
                logger.info(f"⏭️ Existe déjà: {filepath}")
                return public_url
            else:
                logger.error(f"Erreur upload: {e}")
                self.stats['failed'] += 1
                return None
                
    def process_poi_images(self, poi: Dict) -> Dict[str, List[str]]:
        """Traite toutes les images d'un POI"""
        
        processed_images = {
            'thumb': [],
            'card': [],
            'full': [],
            'original': []
        }
        
        # Récupérer les URLs des photos depuis le champ JSON
        photos = poi.get('photos', [])
        if isinstance(photos, str):
            try:
                photos = json.loads(photos)
            except:
                photos = []
                
        if not photos:
            logger.warning(f"Aucune photo pour POI {poi['id']}")
            return processed_images
            
        logger.info(f"📸 Traitement de {len(photos)} photos pour {poi['name']}")
        
        # Limiter à 5 photos par POI pour économiser l'espace
        for i, photo in enumerate(photos[:5]):
            if isinstance(photo, dict):
                photo_url = photo.get('url', photo.get('prefix', '') + 'original' + photo.get('suffix', ''))
            else:
                photo_url = photo
                
            if not photo_url:
                continue
                
            # Télécharger l'image originale
            logger.info(f"  Téléchargement photo {i+1}/{min(len(photos), 5)}")
            original_img = self.download_image(photo_url)
            
            if not original_img:
                continue
                
            # Traiter chaque taille
            for size_name, size_dims in self.IMAGE_SIZES.items():
                # Redimensionner
                if size_dims:
                    resized_img = self.resize_image(original_img.copy(), size_dims)
                else:
                    resized_img = original_img.copy()
                    
                # Optimiser
                optimized_data = self.optimize_image(resized_img)
                
                # Générer le nom de fichier
                filename = self.generate_filename(poi['id'], photo_url, size_name)
                
                # Uploader vers Supabase
                public_url = self.upload_to_supabase(optimized_data, filename)
                
                if public_url:
                    processed_images[size_name].append(public_url)
                    
            # Pause pour éviter de surcharger
            time.sleep(0.1)
            
        return processed_images
        
    def update_database(self, poi_id: int, image_urls: Dict[str, List[str]]) -> bool:
        """Met à jour les URLs d'images dans la base de données"""
        
        try:
            # Connexion DB
            conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                database=os.getenv('DB_NAME', 'yorimichi'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', ''),
                port=int(os.getenv('DB_PORT', 5432))
            )
            
            # Si c'est Supabase
            supabase_url = os.getenv('SUPABASE_URL')
            if supabase_url and 'supabase.co' in supabase_url:
                conn = psycopg2.connect(
                    host=supabase_url.replace('https://', '').split('.')[0] + '.pooler.supabase.com',
                    database='postgres',
                    user='postgres.wkhtvcffqpwqxmlukfix',
                    password=os.getenv('SUPABASE_DB_PASSWORD'),
                    port=6543
                )
                
            cursor = conn.cursor()
            
            # Formater les données pour JSONB
            photos_data = {
                'thumb': image_urls.get('thumb', []),
                'card': image_urls.get('card', []),
                'full': image_urls.get('full', []),
                'original': image_urls.get('original', []),
                'processed_at': datetime.now().isoformat()
            }
            
            # Mettre à jour
            query = """
                UPDATE locations 
                SET photos = %s,
                    updated_at = %s
                WHERE id = %s
            """
            
            cursor.execute(query, [Json(photos_data), datetime.now(), poi_id])
            conn.commit()
            
            logger.info(f"✅ DB mise à jour pour POI {poi_id}")
            return True
            
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
                
    def print_stats(self):
        """Affiche les statistiques"""
        logger.info("\n" + "="*50)
        logger.info("📊 STATISTIQUES IMAGES")
        logger.info("="*50)
        logger.info(f"Images téléchargées: {self.stats['downloaded']}")
        logger.info(f"Images uploadées: {self.stats['uploaded']}")
        logger.info(f"Images skippées: {self.stats['skipped']}")
        logger.info(f"Échecs: {self.stats['failed']}")
        logger.info(f"Taille totale: {self.stats['total_size'] / 1024 / 1024:.2f} MB")
        logger.info("="*50)
        

def process_all_pois(limit: Optional[int] = None, 
                     only_with_photos: bool = True, test_mode: bool = False):
    """Traite tous les POIs avec photos"""
    
    # Configuration Supabase
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not supabase_key:
        logger.error("❌ SUPABASE_URL et SUPABASE_ANON_KEY requis!")
        sys.exit(1)
        
    # Créer le client Supabase
    supabase = create_client(supabase_url, supabase_key)
    
    # Créer le processeur d'images
    processor = ImageProcessor(supabase)
    
    # Connexion DB pour récupérer les POIs
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'yorimichi'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        port=int(os.getenv('DB_PORT', 5432))
    )
    
    # Si c'est Supabase DB
    if supabase_url and 'supabase.co' in supabase_url:
        conn = psycopg2.connect(
            host=supabase_url.replace('https://', '').split('.')[0] + '.pooler.supabase.com',
            database='postgres',
            user='postgres.wkhtvcffqpwqxmlukfix',
            password=os.getenv('SUPABASE_DB_PASSWORD'),
            port=6543
        )
        
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Récupérer les POIs
    query = "SELECT * FROM locations WHERE source_url LIKE '%tokyocheapo%'"
    params = []
    
    if only_with_photos:
        query += " AND photos IS NOT NULL AND photos != '[]'::jsonb"
        
    query += " ORDER BY created_at DESC"
    
    if limit:
        query += f" LIMIT {limit}"
        
    cursor.execute(query, params)
    pois = cursor.fetchall()
    
    total = len(pois)
    logger.info(f"📊 {total} POIs avec photos à traiter")
    
    if test_mode:
        logger.info("🧪 MODE TEST - Traitement sans mise à jour DB")
        
    # Traiter chaque POI
    for i, poi in enumerate(pois, 1):
        logger.info(f"\n[{i}/{total}] {poi['name']}")
        
        # Traiter les images
        image_urls = processor.process_poi_images(dict(poi))
        
        # Mettre à jour la DB
        if not test_mode and any(image_urls.values()):
            processor.update_database(poi['id'], image_urls)
            
        # Checkpoint tous les 10 POIs
        if i % 10 == 0:
            logger.info(f"💾 Checkpoint: {i} POIs traités")
            processor.print_stats()
            
    # Stats finales
    processor.print_stats()
    
    cursor.close()
    conn.close()
    

def main():
    """Point d'entrée principal"""
    
    parser = argparse.ArgumentParser(description='Téléchargement et stockage des images dans Supabase')
    # --platform removed - using source_url filter instead
    parser.add_argument('--limit', type=int, help='Nombre max de POIs à traiter')
    parser.add_argument('--all', action='store_true', help='Traiter tous les POIs (même sans photos)')
    parser.add_argument('--test', action='store_true', help='Mode test (pas de mise à jour DB)')
    
    args = parser.parse_args()
    
    logger.info("🚀 Démarrage du téléchargement des images")
    logger.info(f"Source: Tokyo Cheapo (via source_url)")
    logger.info(f"Limite: {args.limit or 'Aucune'}")
    logger.info(f"Mode test: {args.test}")
    
    process_all_pois(
        limit=args.limit,
        only_with_photos=not args.all,
        test_mode=args.test
    )
    

if __name__ == "__main__":
    # Créer le dossier logs si nécessaire
    os.makedirs('logs', exist_ok=True)
    
    # Installer Pillow si nécessaire
    try:
        import PIL
    except ImportError:
        logger.info("Installation de Pillow...")
        os.system("pip install Pillow")
        
    # Installer supabase si nécessaire
    try:
        import supabase
    except ImportError:
        logger.info("Installation de supabase...")
        os.system("pip install supabase")
        
    main()