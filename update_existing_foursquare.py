#!/usr/bin/env python3
"""
Script pour mettre à jour les POIs qui ont déjà un Foursquare ID
Met à jour: horaires, statut fermé, rating, prix, etc.
Ne re-télécharge pas les photos pour économiser l'espace
"""

import os
import sys
import json
import time
import logging
import argparse
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
import requests

# Créer le dossier logs si nécessaire
os.makedirs('logs', exist_ok=True)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/update_foursquare_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()


class FoursquareUpdater:
    """Met à jour les données Foursquare existantes"""
    
    def __init__(self):
        self.setup_clients()
        self.stats = {
            'total': 0,
            'processed': 0,
            'updated': 0,
            'closed': 0,
            'failed': 0,
            'api_calls': 0,
            'start_time': datetime.now()
        }
        
    def setup_clients(self):
        """Initialise les clients nécessaires"""
        # Foursquare session
        self.foursquare_session = requests.Session()
        self.foursquare_session.headers.update({
            'Authorization': f'Bearer {os.getenv("FOURSQUARE_API_KEY")}',
            'Accept': 'application/json'
        })
        
        # Supabase client
        supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
    def get_place_details(self, fsq_id: str) -> Optional[Dict]:
        """Récupère les détails à jour d'un lieu Foursquare"""
        try:
            url = f"https://api.foursquare.com/v3/places/{fsq_id}"
            params = {
                'fields': 'name,location,categories,rating,price,hours,website,tel,verified,stats,closed_bucket'
            }
            
            response = self.foursquare_session.get(url, params=params, timeout=10)
            self.stats['api_calls'] += 1
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Foursquare error {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"Erreur API Foursquare: {e}")
            
        return None
        
    def update_poi(self, poi: Dict) -> Optional[Dict]:
        """Met à jour les données d'un POI"""
        
        logger.info(f"🔄 [{self.stats['processed']+1}/{self.stats['total']}] {poi['name']}")
        
        # Récupérer les données à jour depuis Foursquare
        fsq_data = self.get_place_details(poi['fsq_id'])
        
        if not fsq_data:
            logger.warning(f"  ❌ Impossible de récupérer les données")
            self.stats['failed'] += 1
            return None
            
        # Préparer les données mises à jour
        updated = {
            'updated_at': datetime.now().isoformat(),
            'last_foursquare_update': datetime.now().isoformat()
        }
        
        # Rating et prix
        if 'rating' in fsq_data:
            updated['rating'] = fsq_data['rating']
        if 'price' in fsq_data:
            updated['price_tier'] = fsq_data['price']
            
        # Horaires et statut d'ouverture
        if 'hours' in fsq_data:
            updated['hours'] = fsq_data['hours']
            updated['open_now'] = fsq_data['hours'].get('open_now')
            
        # Vérifier si fermé définitivement
        # closed_bucket n'existe que si le lieu est vraiment fermé (VenueClosed, VenueRelocated)
        if 'closed_bucket' in fsq_data and fsq_data['closed_bucket'] in ['VenueClosed', 'VenueRelocated']:
            updated['permanently_closed'] = True
            updated['closure_reason'] = fsq_data['closed_bucket']
            logger.warning(f"  ⚠️ POI fermé définitivement: {fsq_data['closed_bucket']}")
            self.stats['closed'] += 1
        else:
            # S'assurer que c'est bien ouvert si pas de closed_bucket valide
            updated['permanently_closed'] = False
            updated['closure_reason'] = None
            
        # Contact (peut avoir changé)
        if 'tel' in fsq_data:
            updated['phone'] = fsq_data['tel']
        if 'website' in fsq_data:
            updated['website'] = fsq_data['website']
            
        # Stats (visiteurs, etc.)
        if 'stats' in fsq_data:
            updated['stats'] = fsq_data['stats']
            
        # Statut vérifié
        if 'verified' in fsq_data:
            updated['verified'] = fsq_data['verified']
            
        # Adresse mise à jour
        if 'location' in fsq_data:
            location = fsq_data['location']
            if location.get('formatted_address'):
                updated['address'] = location['formatted_address']
                
        logger.info(f"  ✅ Données mises à jour")
        self.stats['updated'] += 1
        
        return updated
        
    def process_all(self, limit: Optional[int] = None, test_mode: bool = False, force_all: bool = False):
        """Traite tous les POIs avec fsq_id"""
        
        logger.info("\n" + "="*60)
        logger.info("🔄 MISE À JOUR DES DONNÉES FOURSQUARE EXISTANTES")
        logger.info("="*60)
        
        try:
            # Récupérer tous les POIs avec fsq_id qui ont des champs manquants
            # Priorité : ceux qui n'ont pas permanently_closed (nouveau champ)
            # ou pas de last_foursquare_update (jamais mis à jour)
            # Pagination pour dépasser 1000
            all_pois = []
            offset = 0
            batch_size = 1000
            
            while True:
                query = self.supabase.table('locations').select('*') \
                    .not_.is_('fsq_id', 'null')
                
                # Filtrer ceux qui ont besoin d'update (sauf si force_all)
                if not force_all:
                    # Soit permanently_closed est null (nouveau champ)
                    # Soit pas de last_foursquare_update (jamais mis à jour)
                    # Soit des champs importants manquants
                    query = query.or_(
                        'permanently_closed.is.null,'
                        'last_foursquare_update.is.null,'
                        'hours.is.null,'
                        'rating.is.null,'
                        'open_now.is.null'
                    )
                
                query = query.range(offset, offset + batch_size - 1)
                
                if limit and offset >= limit:
                    break
                    
                result = query.execute()
                batch = result.data
                
                if not batch:
                    break
                    
                all_pois.extend(batch)
                
                if len(batch) < batch_size:
                    break
                    
                offset += batch_size
                logger.info(f"📄 Chargé {len(all_pois)} POIs...")
                
            # Limiter si demandé
            if limit:
                all_pois = all_pois[:limit]
                
            self.stats['total'] = len(all_pois)
            if force_all:
                logger.info(f"📊 {self.stats['total']} POIs avec FSQ ID à mettre à jour (TOUS)")
            else:
                logger.info(f"📊 {self.stats['total']} POIs avec champs manquants à mettre à jour")
            
            if test_mode:
                logger.info("🧪 MODE TEST - Pas de mise à jour DB")
                
            # Traiter chaque POI
            for poi in all_pois:
                self.stats['processed'] += 1
                
                # Mettre à jour les données
                updated_data = self.update_poi(poi)
                
                # Sauvegarder en base
                if updated_data and not test_mode:
                    try:
                        self.supabase.table('locations') \
                            .update(updated_data) \
                            .eq('id', poi['id']) \
                            .execute()
                        logger.info(f"  💾 Base de données mise à jour")
                    except Exception as e:
                        logger.error(f"  ❌ Erreur mise à jour DB: {e}")
                        self.stats['failed'] += 1
                        
                # Rate limiting (50 req/sec max)
                time.sleep(0.02)
                
                # Stats tous les 100 POIs
                if self.stats['processed'] % 100 == 0:
                    self.print_stats()
                    
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
        logger.info(f"Mis à jour: {self.stats['updated']}")
        logger.info(f"Fermés définitivement: {self.stats['closed']}")
        logger.info(f"Échecs: {self.stats['failed']}")
        logger.info(f"Appels API Foursquare: {self.stats['api_calls']}")
        logger.info(f"Durée: {duration:.1f}s ({duration/60:.1f} min)")
        
        if self.stats['processed'] > 0:
            logger.info(f"Vitesse: {self.stats['processed']/duration:.2f} POIs/s")
            
        # Coût Foursquare (toujours gratuit avec $200/mois)
        cost = self.stats['api_calls'] * 0.002
        logger.info(f"Coût Foursquare: ${cost:.2f} (sur $200 gratuits/mois)")


def main():
    """Point d'entrée principal"""
    
    parser = argparse.ArgumentParser(description='Mise à jour des POIs avec Foursquare existant')
    parser.add_argument('--limit', type=int, help='Nombre max de POIs à traiter')
    parser.add_argument('--test', action='store_true', help='Mode test (pas de mise à jour DB)')
    parser.add_argument('--force-all', action='store_true', 
                       help='Forcer la mise à jour de TOUS les POIs (pas seulement ceux avec champs manquants)')
    
    args = parser.parse_args()
    
    # Vérifier les variables d'environnement
    required_vars = []
    
    if not os.getenv('FOURSQUARE_API_KEY'):
        required_vars.append('FOURSQUARE_API_KEY')
        
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    if not supabase_url:
        required_vars.append('SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL')
        
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
    if not supabase_key:
        required_vars.append('SUPABASE_SERVICE_ROLE_KEY')
        
    if required_vars:
        logger.error(f"❌ Variables d'environnement manquantes: {', '.join(required_vars)}")
        sys.exit(1)
        
    # Créer l'updater
    updater = FoursquareUpdater()
    
    # Lancer le traitement
    logger.info("Configuration:")
    logger.info(f"  Limite: {args.limit or 'Aucune'}")
    logger.info(f"  Mode test: {args.test}")
    logger.info(f"  Forcer tous: {args.force_all}")
    logger.info("")
    
    updater.process_all(
        limit=args.limit,
        test_mode=args.test,
        force_all=args.force_all
    )


if __name__ == "__main__":
    main()