#!/usr/bin/env python3
"""
Script ROBUSTE pour fixer les coordonnées manquantes dans la table location
Utilise Jageocoder avec retry, checkpoint, et reprise après échec
"""

import os
import sys
import time
import json
import logging
import signal
from datetime import datetime
from typing import Optional, Tuple, List
from dotenv import load_dotenv
from supabase import create_client

# Configuration du logging
log_filename = f'geocoding_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_filename, encoding='utf-8')
    ]
)
logger = logging.getLogger('GeocodingFixer')

load_dotenv()

class GeocodingFixer:
    """Fixe les coordonnées manquantes avec robustesse et reprise après échec"""
    
    def __init__(self, checkpoint_file='geocoding_checkpoint.json'):
        self.checkpoint_file = checkpoint_file
        self.checkpoint_data = self.load_checkpoint()
        self.interrupted = False
        
        # Gestion de Ctrl+C propre
        signal.signal(signal.SIGINT, self.handle_interrupt)
        
        # Stats
        self.stats = self.checkpoint_data.get('stats', {
            'total': 0,
            'fixed': 0, 
            'failed': 0,
            'skipped': 0,
            'processed_ids': []
        })
        
        logger.info(f"📝 Fichier de log: {log_filename}")
        
        # Connexion Supabase avec retry
        self.init_supabase_with_retry()
        
        # Jageocoder avec fallback
        self.init_jageocoder_with_retry()
    
    def handle_interrupt(self, signum, frame):
        """Gestion propre de l'interruption (Ctrl+C)"""
        logger.warning("\n⚠️ Interruption détectée - Sauvegarde en cours...")
        self.interrupted = True
        self.save_checkpoint()
        logger.info("💾 Checkpoint sauvegardé. Relancez le script pour reprendre.")
        sys.exit(0)
    
    def init_supabase_with_retry(self, max_retries=3):
        """Initialise Supabase avec retry"""
        for attempt in range(max_retries):
            try:
                self.supabase = create_client(
                    os.getenv('SUPABASE_URL'),
                    os.getenv('SUPABASE_KEY')
                )
                # Test connection
                self.supabase.table('place').select('id').limit(1).execute()
                logger.info("✅ Connexion Supabase établie")
                return
            except Exception as e:
                logger.warning(f"Tentative {attempt+1}/{max_retries} échouée: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error("❌ Impossible de se connecter à Supabase")
                    sys.exit(1)
    
    def init_jageocoder_with_retry(self, max_retries=3):
        """Initialise Jageocoder avec retry et fallback"""
        try:
            import jageocoder
            self.jageocoder = jageocoder
            
            for attempt in range(max_retries):
                try:
                    jageocoder.init(url='https://jageocoder.info-proto.com/jsonrpc')
                    # Test avec une adresse simple
                    test = jageocoder.search("Tokyo")
                    if test:
                        logger.info("✅ Jageocoder initialisé (serveur distant)")
                        self.jageocoder_available = True
                        return
                except Exception as e:
                    logger.warning(f"Jageocoder tentative {attempt+1}/{max_retries}: {e}")
                    time.sleep(2)
                    
            logger.warning("⚠️ Jageocoder indisponible - Mode dégradé activé")
            self.jageocoder_available = False
            
        except ImportError:
            logger.error("❌ Jageocoder n'est pas installé!")
            logger.error("👉 Installation: pip install jageocoder")
            sys.exit(1)
    
    def load_checkpoint(self) -> dict:
        """Charge le checkpoint pour reprendre après interruption"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    data = json.load(f)
                    logger.info(f"📂 Checkpoint trouvé: {data['stats']['fixed']} POIs déjà traités")
                    return data
            except Exception as e:
                logger.warning(f"Checkpoint corrompu: {e}")
        return {'stats': {'total': 0, 'fixed': 0, 'failed': 0, 'skipped': 0, 'processed_ids': []}}
    
    def save_checkpoint(self):
        """Sauvegarde l'état pour pouvoir reprendre"""
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump({
                    'stats': self.stats,
                    'timestamp': datetime.now().isoformat()
                }, f, indent=2)
            logger.debug(f"Checkpoint sauvegardé: {self.stats['fixed']} fixes")
        except Exception as e:
            logger.error(f"Erreur sauvegarde checkpoint: {e}")
    
    def preprocess_address(self, address: str) -> str:
        """Prétraite l'adresse pour optimiser Jageocoder"""
        if not address:
            return ""
        
        # Format typique: "28-6 Udagawacho, Shibuya City, Tokyo 150-0042, Japan"
        # Jageocoder fonctionne mieux sans ", Japan" à la fin
        address = address.replace(", Japan", "").strip()
        
        # Normaliser Tokyo
        address = address.replace("Tōkyō", "Tokyo")
        address = address.replace("Tokyo Metropolis", "Tokyo")
        address = address.replace("Kōtō-ku", "Koto-ku")
        address = address.replace("Ōta-ku", "Ota-ku")
        address = address.replace("Chūō-ku", "Chuo-ku")
        
        return address.strip()
    
    def geocode_with_retry(self, address: str, max_retries: int = 3) -> Optional[Tuple[float, float]]:
        """Geocode avec retry automatique"""
        if not address or not self.jageocoder_available:
            return None
        
        # Nettoyer l'adresse
        processed = self.preprocess_address(address)
        logger.debug(f"Adresse originale: {address}")
        logger.debug(f"Adresse traitée: {processed}")
        
        for attempt in range(max_retries):
            try:
                results = self.jageocoder.search(processed)
                
                if results and len(results) > 0:
                    node = results[0].get('node', {})
                    if 'x' in node and 'y' in node:
                        lat, lng = float(node['y']), float(node['x'])
                        
                        # Validation Tokyo (élargi pour inclure la périphérie)
                        if 35.4 < lat < 36.0 and 139.3 < lng < 140.1:
                            logger.debug(f"Coordonnées trouvées: lat={lat}, lng={lng}")
                            return lat, lng
                        else:
                            logger.warning(f"Coordonnées hors zone Tokyo: {lat}, {lng}")
                        
                return None  # Pas trouvé
                
            except Exception as e:
                logger.debug(f"Tentative {attempt+1} échouée pour '{processed[:30]}...': {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Pause avant retry
                    
        return None
    
    def get_pois_batch(self, batch_size: int = 100, offset: int = 0, platform: Optional[str] = None) -> List[dict]:
        """Récupère les POIs par batch pour économiser la mémoire"""
        try:
            query = self.supabase.table('place').select('id, name, address, latitude, longitude, platform')
            
            # Filtrer par platform si spécifié
            if platform and platform != 'all':
                query = query.eq('platform', platform)
            
            # POIs sans coordonnées ou avec 0,0
            query = query.or_('latitude.is.null,longitude.is.null,and(latitude.eq.0,longitude.eq.0)')
            query = query.range(offset, offset + batch_size - 1)
            
            response = query.execute()
            return response.data
        except Exception as e:
            logger.error(f"Erreur récupération batch: {e}")
            return []
    
    def update_poi_with_retry(self, poi_id: int, lat: float, lng: float, max_retries: int = 3) -> bool:
        """Met à jour un POI avec retry"""
        for attempt in range(max_retries):
            try:
                self.supabase.table('place').update({
                    'latitude': lat,
                    'longitude': lng
                }).eq('id', poi_id).execute()
                return True
            except Exception as e:
                logger.warning(f"Tentative {attempt+1} échouée pour POI {poi_id}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    # Reconnecter si nécessaire
                    if "connection" in str(e).lower():
                        self.init_supabase_with_retry()
        return False
    
    def display_progress(self, current: int, total: int, fixed: int, failed: int):
        """Affiche une barre de progression"""
        if total == 0:
            return
            
        percent = current * 100 / total if total > 0 else 0
        bar_length = 40
        filled_length = int(bar_length * current // total) if total > 0 else 0
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        print(f'\r📊 |{bar}| {percent:.1f}% ({current}/{total}) ✅ {fixed} ❌ {failed}', end='', flush=True)
    
    def process_all(self, limit: Optional[int] = None, test_mode: bool = False, platform: str = 'all'):
        """Traite tous les POIs avec reprise après échec"""
        print("\n" + "="*70)
        print("     🗾 GEOCODING FIXER (ROBUST)")
        if platform != 'all':
            print(f"     Platform: {platform}")
        print("="*70)
        
        batch_size = 100
        offset = 0
        total_processed = 0
        start_time = time.time()
        
        # Si reprise, afficher info
        if self.stats['processed_ids']:
            print(f"🔄 Reprise: {len(self.stats['processed_ids'])} POIs déjà traités")
            print(f"   ✅ {self.stats['fixed']} fixes")
            print(f"   ❌ {self.stats['failed']} échecs")
            print("-"*70)
        
        while True:
            if self.interrupted:
                break
                
            # Récupérer un batch
            pois = self.get_pois_batch(batch_size, offset, platform)
            
            if not pois or (limit and total_processed >= limit):
                break
            
            for poi in pois:
                if self.interrupted:
                    break
                    
                # Skip si déjà traité (reprise après crash)
                if poi['id'] in self.stats['processed_ids']:
                    self.stats['skipped'] += 1
                    continue
                
                # Skip si coordonnées valides
                if (poi.get('latitude') and poi.get('longitude') and 
                    poi['latitude'] != 0 and poi['longitude'] != 0):
                    self.stats['skipped'] += 1
                    self.stats['processed_ids'].append(poi['id'])
                    continue
                
                # Skip si pas d'adresse
                if not poi.get('address'):
                    self.stats['failed'] += 1
                    self.stats['processed_ids'].append(poi['id'])
                    logger.warning(f"Pas d'adresse pour POI {poi['id']}: {poi['name'][:40]}")
                    continue
                
                # Geocoder avec retry
                coords = self.geocode_with_retry(poi['address'])
                
                if coords:
                    lat, lng = coords
                    
                    if not test_mode:
                        if self.update_poi_with_retry(poi['id'], lat, lng):
                            self.stats['fixed'] += 1
                            logger.info(f"✅ POI {poi['id']}: {poi['name'][:40]} ({poi.get('platform')}): {lat:.6f}, {lng:.6f}")
                        else:
                            self.stats['failed'] += 1
                            logger.error(f"❌ Échec update POI {poi['id']}")
                    else:
                        self.stats['fixed'] += 1
                        logger.info(f"🧪 TEST: {poi['name'][:40]} → {lat:.6f}, {lng:.6f}")
                else:
                    self.stats['failed'] += 1
                    logger.debug(f"Geocoding échoué pour: {poi['address']}")
                
                # Marquer comme traité
                self.stats['processed_ids'].append(poi['id'])
                total_processed += 1
                
                # Afficher progress
                self.display_progress(total_processed, 
                                    total_processed + 100,  # Estimation
                                    self.stats['fixed'], 
                                    self.stats['failed'])
                
                # Sauvegarder checkpoint tous les 50 POIs
                if total_processed % 50 == 0:
                    self.save_checkpoint()
                    print()  # Nouvelle ligne
                    logger.info(f"💾 Checkpoint sauvegardé ({self.stats['fixed']} fixes)")
                
                if limit and total_processed >= limit:
                    break
            
            offset += batch_size
        
        # Clear progress bar
        print("\n")
        
        # Sauvegarde finale
        self.save_checkpoint()
        
        # Calcul durée
        duration = time.time() - start_time
        
        # Résumé
        print("\n" + "="*70)
        print("                    📊 RÉSULTATS FINAUX")
        print("="*70)
        print(f"""
  🎯 Total traité:     {total_processed:>6}
  ✅ Corrigés:         {self.stats['fixed']:>6} ({self.stats['fixed']*100/max(total_processed,1):.1f}%)
  ⏭️  Skippés:          {self.stats['skipped']:>6}
  ❌ Échoués:          {self.stats['failed']:>6}
  
  ⏱️  Durée:            {int(duration//60)}m {int(duration%60)}s
  ⚡ Vitesse:          {total_processed/max(duration,1):.1f} POIs/sec
  
  📝 Log complet:      {log_filename}
        """)
        print("="*70)
        
        if self.stats['fixed'] > 0:
            print(f"\n🎉 {self.stats['fixed']} POIs ont maintenant des coordonnées précises!")
        
        # Nettoyer checkpoint si tout est fini et pas en mode test
        if not self.interrupted and not test_mode and total_processed > 0:
            if input("\n🗑️ Supprimer le checkpoint? (y/n): ").lower() == 'y':
                try:
                    os.remove(self.checkpoint_file)
                    logger.info("Checkpoint supprimé")
                except:
                    pass

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='🗾 Fix les coordonnées manquantes avec Jageocoder (ROBUST)'
    )
    parser.add_argument(
        '--limit', 
        type=int, 
        help='Limiter le nombre de POIs à traiter'
    )
    parser.add_argument(
        '--test', 
        action='store_true', 
        help='Mode test - affiche sans sauvegarder'
    )
    parser.add_argument(
        '--platform',
        type=str,
        choices=['tokyo_cheapo', 'google_places', 'all'],
        default='all',
        help='Platform à traiter (default: all)'
    )
    parser.add_argument(
        '--reset', 
        action='store_true', 
        help='Reset le checkpoint pour recommencer'
    )
    
    args = parser.parse_args()
    
    # Reset checkpoint si demandé
    if args.reset and os.path.exists('geocoding_checkpoint.json'):
        os.remove('geocoding_checkpoint.json')
        print("✅ Checkpoint réinitialisé")
    
    # Vérifier que jageocoder est installé
    try:
        import jageocoder
    except ImportError:
        print("\n❌ Jageocoder n'est pas installé!")
        print("\n📦 Installation:")
        print("   pip install jageocoder")
        print("\n📚 Plus d'infos: https://github.com/t-sagara/jageocoder")
        sys.exit(1)
    
    # Lancer le fix
    fixer = GeocodingFixer()
    fixer.process_all(
        limit=args.limit, 
        test_mode=args.test,
        platform=args.platform
    )

if __name__ == "__main__":
    main()