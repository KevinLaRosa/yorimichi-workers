#!/usr/bin/env python3
"""
Script pour traduire les adresses japonaises en romaji avec GPT-4o-mini
"""

import os
import sys
import json
import time
import logging
import argparse
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
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
        logging.FileHandler(f'logs/translate_romaji_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
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
class TranslatorConfig:
    """Configuration pour la traduction en romaji"""
    openai_api_key: str
    supabase_url: str
    supabase_key: str
    batch_size: int = 10  # Traiter par lots pour économiser les appels API
    rate_limit: int = 3  # req/sec pour OpenAI

class RomajiTranslator:
    """Traduit les adresses japonaises en romaji avec GPT-4o-mini"""
    
    def __init__(self, config: TranslatorConfig):
        self.config = config
        self.setup_clients()
        self.stats = {
            'total': 0,
            'processed': 0,
            'translated': 0,
            'skipped': 0,
            'failed': 0,
            'api_calls': 0,
            'start_time': datetime.now()
        }
        
    def setup_clients(self):
        """Initialise les clients nécessaires"""
        # Supabase client
        self.supabase: Client = create_client(
            self.config.supabase_url,
            self.config.supabase_key
        )
        
        # OpenAI client
        self.openai_client = OpenAI(api_key=self.config.openai_api_key)
        
    def translate_batch_to_romaji(self, addresses: List[Dict]) -> Dict[str, str]:
        """Traduit un lot d'adresses en romaji avec GPT-4o-mini"""
        
        if not addresses:
            return {}
            
        try:
            # Préparer le prompt pour GPT
            addresses_json = []
            for addr in addresses:
                addresses_json.append({
                    'id': addr['id'],
                    'address': addr['address'] or addr['name']  # Utiliser le nom si pas d'adresse
                })
                
            prompt = f"""Tu es un expert en traduction japonais-romaji. 
Traduis ces adresses japonaises en romaji (romanisation Hepburn).
Garde la structure de l'adresse (quartier, ville, etc.) mais traduis en caractères latins.
Pour les noms de lieux célèbres, utilise la romanisation officielle si elle existe.

Adresses à traduire :
{json.dumps(addresses_json, indent=2, ensure_ascii=False)}

Réponds UNIQUEMENT avec un JSON dans ce format exact :
{{
  "id1": "adresse traduite en romaji",
  "id2": "adresse traduite en romaji",
  ...
}}

Important:
- Utilise la romanisation Hepburn standard
- Garde les numéros tels quels
- Pour Tokyo, utilise "Tokyo" pas "Tōkyō"
- Pour les quartiers connus, utilise l'orthographe commune (Shibuya, Shinjuku, etc.)
- Si l'adresse est déjà en romaji ou contient beaucoup de romaji, retourne-la telle quelle
"""

            # Appeler GPT-4o-mini
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Tu es un expert en romanisation du japonais. Tu utilises le système Hepburn modifié."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Basse température pour cohérence
                max_tokens=2000,
                response_format={"type": "json_object"}  # Forcer une réponse JSON
            )
            self.stats['api_calls'] += 1
            
            # Parser la réponse
            content = response.choices[0].message.content.strip()
            
            # Essayer de parser le JSON
            try:
                translations = json.loads(content)
                logger.info(f"  ✅ {len(translations)} adresses traduites")
                return translations
            except json.JSONDecodeError as e:
                logger.error(f"  ❌ Erreur parsing JSON: {e}")
                logger.error(f"  Réponse GPT: {content}")
                return {}
                
        except Exception as e:
            logger.error(f"Erreur traduction GPT: {e}")
            return {}
            
    def process_all(self, limit: Optional[int] = None, force_update: bool = False, test_mode: bool = False):
        """Traite tous les POIs pour traduire les adresses en romaji"""
        
        logger.info("\n" + "="*60)
        logger.info("🔤 TRADUCTION DES ADRESSES EN ROMAJI")
        logger.info("="*60)
        
        try:
            # Récupérer les POIs qui ont une adresse mais pas de romaji
            query = self.supabase.table('locations').select('id, name, address, address_romaji')
            
            if not force_update:
                # Ne traiter que ceux qui n'ont pas encore de romaji
                query = query.is_('address_romaji', 'null')
                
            # Exclure ceux qui n'ont pas d'adresse du tout
            query = query.not_.is_('address', 'null')
            
            if limit:
                query = query.limit(limit)
                
            result = query.execute()
            pois = result.data
            
            # Filtrer ceux qui ont déjà une adresse en romaji (si elle existe déjà)
            if not force_update:
                pois_to_process = []
                for poi in pois:
                    # Vérifier si l'adresse contient déjà beaucoup de caractères latins
                    if poi['address']:
                        # Compter les caractères ASCII vs non-ASCII
                        ascii_count = sum(1 for c in poi['address'] if ord(c) < 128)
                        total_count = len(poi['address'])
                        
                        # Si plus de 70% de caractères ASCII, probablement déjà en romaji
                        if total_count > 0 and ascii_count / total_count > 0.7:
                            logger.info(f"⏭️ {poi['name']} - Adresse déjà en romaji")
                            self.stats['skipped'] += 1
                        else:
                            pois_to_process.append(poi)
                    else:
                        pois_to_process.append(poi)
            else:
                pois_to_process = pois
                
            self.stats['total'] = len(pois_to_process)
            logger.info(f"📊 {self.stats['total']} POIs à traduire")
            
            if test_mode:
                logger.info("🧪 MODE TEST - Pas de mise à jour DB")
                
            # Traiter par lots pour économiser les appels API
            for i in range(0, len(pois_to_process), self.config.batch_size):
                batch = pois_to_process[i:i+self.config.batch_size]
                batch_num = (i // self.config.batch_size) + 1
                total_batches = (len(pois_to_process) + self.config.batch_size - 1) // self.config.batch_size
                
                logger.info(f"\n{'='*60}")
                logger.info(f"📦 Batch {batch_num}/{total_batches} ({len(batch)} POIs)")
                
                # Traduire le lot
                translations = self.translate_batch_to_romaji(batch)
                
                if translations:
                    # Mettre à jour la base de données
                    for poi in batch:
                        self.stats['processed'] += 1
                        
                        if str(poi['id']) in translations:
                            romaji_address = translations[str(poi['id'])]
                            
                            if not test_mode:
                                try:
                                    # Mettre à jour avec le SDK Supabase
                                    self.supabase.table('locations') \
                                        .update({
                                            'address_romaji': romaji_address,
                                            'romaji_translated_at': datetime.now().isoformat()
                                        }) \
                                        .eq('id', poi['id']) \
                                        .execute()
                                    
                                    logger.info(f"  ✅ {poi['name']}: {romaji_address}")
                                    self.stats['translated'] += 1
                                    
                                except Exception as e:
                                    logger.error(f"  ❌ Erreur mise à jour {poi['name']}: {e}")
                                    self.stats['failed'] += 1
                            else:
                                logger.info(f"  🧪 [TEST] {poi['name']}: {romaji_address}")
                                self.stats['translated'] += 1
                        else:
                            logger.warning(f"  ⚠️ Pas de traduction pour {poi['name']}")
                            self.stats['failed'] += 1
                            
                # Rate limiting
                time.sleep(1 / self.config.rate_limit)
                
                # Checkpoint tous les 10 lots
                if batch_num % 10 == 0:
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
        logger.info(f"Traduits: {self.stats['translated']}")
        logger.info(f"Skippés (déjà romaji): {self.stats['skipped']}")
        logger.info(f"Échecs: {self.stats['failed']}")
        logger.info(f"Appels API OpenAI: {self.stats['api_calls']}")
        logger.info(f"Durée: {duration:.1f}s ({duration/60:.1f} min)")
        
        if self.stats['processed'] > 0:
            success_rate = (self.stats['translated'] / self.stats['processed']) * 100
            logger.info(f"Taux de succès: {success_rate:.1f}%")
            
        # Estimation du coût OpenAI (GPT-4o-mini)
        # Prix approximatif: $0.15 per 1M input tokens, $0.60 per 1M output tokens
        # Estimation: ~500 tokens par requête en moyenne
        estimated_cost = self.stats['api_calls'] * 0.0003  # Très approximatif
        logger.info(f"Coût estimé OpenAI: ${estimated_cost:.4f}")


def main():
    """Point d'entrée principal"""
    
    parser = argparse.ArgumentParser(description='Traduction des adresses en romaji avec GPT-4o-mini')
    parser.add_argument('--limit', type=int, help='Nombre max de POIs à traiter')
    parser.add_argument('--batch-size', type=int, default=10, help='Taille des lots (défaut: 10)')
    parser.add_argument('--test', action='store_true', help='Mode test (pas de mise à jour DB)')
    parser.add_argument('--force-update', action='store_true', help='Forcer la retraduction même si romaji existe')
    
    args = parser.parse_args()
    
    # Vérifier les variables d'environnement
    required_vars = []
    
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
        logger.info("OPENAI_API_KEY=your_openai_key")
        logger.info("NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co")
        logger.info("SUPABASE_SERVICE_ROLE_KEY=your_service_role_key")
        sys.exit(1)
        
    # Configuration
    config = TranslatorConfig(
        openai_api_key=os.getenv('OPENAI_API_KEY'),
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        batch_size=args.batch_size
    )
    
    # Créer le traducteur
    translator = RomajiTranslator(config)
    
    # Lancer le traitement
    logger.info("Configuration:")
    logger.info(f"  Limite: {args.limit or 'Aucune'}")
    logger.info(f"  Taille des lots: {args.batch_size}")
    logger.info(f"  Mode test: {args.test}")
    logger.info(f"  Forcer mise à jour: {args.force_update}")
    logger.info("")
    
    translator.process_all(
        limit=args.limit,
        test_mode=args.test,
        force_update=args.force_update
    )


if __name__ == "__main__":
    main()