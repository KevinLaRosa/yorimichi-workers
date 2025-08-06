#!/usr/bin/env python3
"""
Script pour mettre à jour les embeddings APRÈS l'enrichissement Foursquare
Plus économique de le faire une fois à la fin avec toutes les nouvelles données
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI

# Créer le dossier logs si nécessaire
os.makedirs('logs', exist_ok=True)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/update_embeddings_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
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

class EmbeddingUpdater:
    """Met à jour les embeddings après enrichissement"""
    
    def __init__(self):
        # OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("❌ OPENAI_API_KEY non définie!")
            sys.exit(1)
        self.openai_client = OpenAI(api_key=api_key)
        
        # Database config
        supabase_url = os.getenv('SUPABASE_URL')
        if not supabase_url:
            logger.error("❌ SUPABASE_URL non définie!")
            sys.exit(1)
            
        project_id = supabase_url.replace('https://', '').split('.')[0]
        self.db_config = {
            'host': f"{project_id}.pooler.supabase.com",
            'database': 'postgres',
            'user': f"postgres.{project_id}",
            'password': os.getenv('SUPABASE_DB_PASSWORD'),
            'port': 6543
        }
        
        self.stats = {
            'total': 0,
            'updated': 0,
            'skipped': 0,
            'failed': 0,
            'cost': 0.0
        }
        
    def connect_db(self):
        """Connexion à la base de données"""
        return psycopg2.connect(**self.db_config)
        
    def generate_embedding_text(self, poi: Dict) -> str:
        """Génère le texte optimisé pour l'embedding avec les nouvelles données Foursquare"""
        
        parts = []
        
        # Nom et catégorie
        if poi.get('name'):
            parts.append(f"Name: {poi['name']}")
        if poi.get('category'):
            parts.append(f"Category: {poi['category']}")
        if poi.get('fsq_categories'):
            parts.append(f"Types: {', '.join(poi['fsq_categories'])}")
            
        # Description originale
        if poi.get('description'):
            parts.append(f"Description: {poi['description'][:500]}")
            
        # Localisation enrichie
        if poi.get('address'):
            parts.append(f"Address: {poi['address']}")
        if poi.get('district'):
            parts.append(f"District: {poi['district']}")
            
        # Métadonnées Foursquare
        if poi.get('rating'):
            parts.append(f"Rating: {poi['rating']}/10")
        if poi.get('price_tier'):
            price_symbols = '¥' * poi['price_tier']
            parts.append(f"Price: {price_symbols}")
        if poi.get('verified'):
            parts.append("Verified venue")
            
        # Features et amenities
        if poi.get('amenities'):
            parts.append(f"Features: {', '.join(poi['amenities'][:10])}")
            
        # Horaires
        if poi.get('hours_display'):
            parts.append(f"Hours: {poi['hours_display']}")
        elif poi.get('opening_hours'):
            # Extraire un résumé des horaires
            hours = poi['opening_hours']
            if isinstance(hours, dict) and hours:
                open_days = [day for day, info in hours.items() if info.get('open')]
                if open_days:
                    parts.append(f"Open: {', '.join(open_days[:3])}")
                    
        # Tags et features spéciaux
        if poi.get('features'):
            if isinstance(poi['features'], list):
                features_text = ', '.join(poi['features'][:5])
                parts.append(f"Special: {features_text}")
                
        # Statistiques de popularité
        if poi.get('stats'):
            if isinstance(poi['stats'], dict):
                total_visits = poi['stats'].get('total_visits', 0)
                if total_visits > 1000:
                    parts.append(f"Popular venue with {total_visits} visits")
                    
        return " | ".join(parts)[:8000]  # Limite OpenAI
        
    def update_embedding(self, poi: Dict) -> bool:
        """Met à jour l'embedding d'un POI"""
        
        try:
            # Générer le texte enrichi
            embedding_text = self.generate_embedding_text(poi)
            
            # Créer l'embedding
            response = self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=embedding_text
            )
            embedding = response.data[0].embedding
            self.stats['cost'] += 0.0004  # Coût par embedding
            
            # Mettre à jour dans la base
            conn = self.connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE locations 
                SET embedding = %s,
                    updated_at = %s
                WHERE id = %s
            """, [embedding, datetime.now(), poi['id']])
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.stats['updated'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Erreur embedding pour {poi['name']}: {e}")
            self.stats['failed'] += 1
            return False
            
    def process_batch(self, only_enriched: bool = True, limit: Optional[int] = None,
                     test_mode: bool = False):
        """Traite un batch de POIs"""
        
        logger.info("="*60)
        logger.info("🔄 MISE À JOUR DES EMBEDDINGS")
        logger.info("="*60)
        
        conn = self.connect_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Récupérer les POIs enrichis
        query = """
            SELECT id, name, description, address, district, category,
                   rating, price_tier, verified, amenities, features,
                   opening_hours, hours_display, stats, fsq_categories,
                   metadata
            FROM locations 
            WHERE source_url IS NOT NULL
        """
        
        if only_enriched:
            query += " AND fsq_id IS NOT NULL"
            
        query += " ORDER BY fsq_enriched_at DESC"
        
        if limit:
            query += f" LIMIT {limit}"
            
        cursor.execute(query)
        pois = cursor.fetchall()
        
        self.stats['total'] = len(pois)
        logger.info(f"📊 {self.stats['total']} POIs à traiter")
        
        if test_mode:
            logger.info("🧪 MODE TEST - Génération du texte seulement")
            
        for i, poi in enumerate(pois, 1):
            logger.info(f"[{i}/{self.stats['total']}] {poi['name']}")
            
            if test_mode:
                # Juste afficher le texte qui serait utilisé
                text = self.generate_embedding_text(dict(poi))
                logger.info(f"  Texte ({len(text)} chars): {text[:200]}...")
                self.stats['skipped'] += 1
            else:
                # Mettre à jour réellement
                self.update_embedding(dict(poi))
                
            # Stats tous les 50
            if i % 50 == 0:
                self.print_stats()
                
        cursor.close()
        conn.close()
        
        self.print_stats()
        
    def print_stats(self):
        """Affiche les statistiques"""
        logger.info("\n" + "="*60)
        logger.info("📊 STATISTIQUES")
        logger.info("="*60)
        logger.info(f"Total: {self.stats['total']}")
        logger.info(f"Mis à jour: {self.stats['updated']}")
        logger.info(f"Skippés: {self.stats['skipped']}")
        logger.info(f"Échecs: {self.stats['failed']}")
        logger.info(f"Coût estimé: ${self.stats['cost']:.2f}")
        logger.info("="*60)


def main():
    """Point d'entrée principal"""
    
    parser = argparse.ArgumentParser(description='Mise à jour des embeddings après enrichissement')
    parser.add_argument('--limit', type=int, help='Nombre max de POIs à traiter')
    parser.add_argument('--all', action='store_true', 
                       help='Traiter tous les POIs (pas seulement les enrichis)')
    parser.add_argument('--test', action='store_true', 
                       help='Mode test (génère le texte sans créer embeddings)')
    
    args = parser.parse_args()
    
    updater = EmbeddingUpdater()
    
    logger.info("Configuration:")
    logger.info(f"  Limite: {args.limit or 'Aucune'}")
    logger.info(f"  Seulement enrichis: {not args.all}")
    logger.info(f"  Mode test: {args.test}")
    logger.info("")
    
    # Estimation du coût
    if not args.test and not args.limit:
        logger.warning("⚠️ ATTENTION: Mise à jour de TOUS les embeddings")
        logger.warning("   Coût estimé: ~$0.85 pour 2141 POIs")
        logger.warning("   Utilisez --limit 10 pour tester d'abord")
        input("   Appuyez sur Entrée pour continuer ou Ctrl+C pour annuler...")
    
    updater.process_batch(
        only_enriched=not args.all,
        limit=args.limit,
        test_mode=args.test
    )
    

if __name__ == "__main__":
    # Créer le dossier logs
    os.makedirs('logs', exist_ok=True)
    main()