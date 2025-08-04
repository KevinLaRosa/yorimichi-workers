#!/usr/bin/env python3
"""
Worker Intelligent Yorimichi V3 - SMART EDITION
Version optimisée qui combine qualité premium et économie intelligente
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import traceback

# Imports externes
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client, Client
import openai
from openai import OpenAI

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('yorimichi_crawler_smart.log')
    ]
)
logger = logging.getLogger('YorimichiSmartCrawler')


class YorimichiSmartCrawler:
    """Agent intelligent avec stratégie optimisée qualité/coût"""
    
    # Sitemaps prioritaires (les meilleurs POIs d'abord)
    PRIORITY_SITEMAPS = {
        'high': [
            "https://tokyocheapo.com/place-sitemap1.xml",  # Attractions principales
            "https://tokyocheapo.com/place-sitemap2.xml",
            "https://tokyocheapo.com/place-sitemap3.xml",
        ],
        'medium': [
            "https://tokyocheapo.com/restaurant-sitemap1.xml",  # Restos populaires
            "https://tokyocheapo.com/accommodation-sitemap.xml",  # Hotels
        ],
        'low': [
            "https://tokyocheapo.com/restaurant-sitemap2.xml",  # Autres restos
            "https://tokyocheapo.com/event-sitemap1.xml",  # Events (temporaires)
            "https://tokyocheapo.com/event-sitemap2.xml",
            "https://tokyocheapo.com/tour-sitemap.xml",
        ]
    }
    
    def __init__(self, quality_mode='smart'):
        """
        Modes disponibles:
        - 'smart': GPT-3.5 pour classification, GPT-4 pour les POIs confirmés
        - 'premium': GPT-4 pour tout (plus cher)
        - 'economy': GPT-3.5 pour tout (moins cher)
        """
        # Charger les variables d'environnement
        if os.path.exists('.env.local'):
            load_dotenv('.env.local')
        else:
            load_dotenv()
        
        # Validation des variables d'environnement
        self.validate_environment()
        
        # Initialisation des clients
        self.supabase = create_client(
            os.getenv('NEXT_PUBLIC_SUPABASE_URL'),
            os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        )
        
        # Configuration OpenAI
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Configuration ScrapingBee
        self.scrapingbee_api_key = os.getenv('SCRAPINGBEE_API_KEY')
        
        # Mode de qualité
        self.quality_mode = quality_mode
        
        # Configuration des modèles selon le mode
        if quality_mode == 'premium':
            self.classification_model = "gpt-4-turbo-preview"
            self.generation_model = "gpt-4-turbo-preview"
            self.cost_per_url = 0.10
        elif quality_mode == 'economy':
            self.classification_model = "gpt-3.5-turbo"
            self.generation_model = "gpt-3.5-turbo"
            self.cost_per_url = 0.02
        else:  # smart (par défaut)
            self.classification_model = "gpt-3.5-turbo"
            self.generation_model = "gpt-4-turbo-preview"
            self.cost_per_url = 0.05
        
        # Paramètres
        self.site_name = "Tokyo Cheapo"
        self.agent_name = f"Smart Crawler V3 ({quality_mode} mode)"
        self.batch_log_interval = 25
        self.delay_between_urls = 1.5
        
        # Compteurs
        self.processed_count = 0
        self.success_count = 0
        self.skip_count = 0
        self.error_count = 0
        self.total_cost_estimate = 0.0
        
    def validate_environment(self):
        """Valide que toutes les variables d'environnement requises sont présentes"""
        required_vars = [
            'NEXT_PUBLIC_SUPABASE_URL',
            'SUPABASE_SERVICE_ROLE_KEY',
            'OPENAI_API_KEY',
            'SCRAPINGBEE_API_KEY'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            error_msg = f"Variables d'environnement manquantes: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise EnvironmentError(error_msg)
            
        logger.info("✅ Toutes les variables d'environnement sont configurées")
        
    def verify_database_schema(self) -> Dict[str, bool]:
        """Vérifie que le schéma de base de données est compatible"""
        verification_results = {
            'locations_table': False,
            'processed_urls_table': False,
            'agent_logs_table': False,
            'match_locations_function': False,
            'embedding_column': False
        }
        
        try:
            # Vérifier la table locations
            test_query = self.supabase.table('locations').select('id').limit(1).execute()
            verification_results['locations_table'] = True
            
            # Vérifier les colonnes requises
            # Pour l'instant on assume qu'elles existent si la table existe
            verification_results['embedding_column'] = True
            
        except Exception as e:
            logger.error(f"❌ Table 'locations' non trouvée: {str(e)}")
            
        try:
            # Vérifier processed_urls
            self.supabase.table('processed_urls').select('url').limit(1).execute()
            verification_results['processed_urls_table'] = True
        except Exception as e:
            logger.error(f"❌ Table 'processed_urls' non trouvée: {str(e)}")
            
        try:
            # Vérifier agent_logs
            self.supabase.table('agent_logs').select('id').limit(1).execute()
            verification_results['agent_logs_table'] = True
        except Exception as e:
            logger.error(f"❌ Table 'agent_logs' non trouvée: {str(e)}")
            
        # Afficher le résumé
        all_ok = all(verification_results.values())
        
        if all_ok:
            logger.info("✅ Schéma de base de données vérifié - Tout est OK!")
        else:
            logger.error("❌ Problèmes détectés dans le schéma:")
            for check, status in verification_results.items():
                if not status:
                    logger.error(f"  - {check}: MANQUANT")
                    
        return verification_results
        
    def estimate_costs(self, priority='all') -> Dict[str, Any]:
        """Estime les coûts avant de lancer le crawl"""
        try:
            # Compter les URLs selon la priorité
            url_counts = {
                'high': 0,
                'medium': 0,
                'low': 0
            }
            
            priorities_to_check = []
            if priority == 'all':
                priorities_to_check = ['high', 'medium', 'low']
            elif priority in ['high', 'medium', 'low']:
                priorities_to_check = [priority]
                
            total_urls = 0
            
            for prio in priorities_to_check:
                for sitemap_url in self.PRIORITY_SITEMAPS.get(prio, []):
                    try:
                        response = requests.get(sitemap_url, timeout=30)
                        soup = BeautifulSoup(response.content, 'xml')
                        urls = soup.find_all('loc')
                        url_counts[prio] += len(urls)
                        total_urls += len(urls)
                    except:
                        continue
                        
            # Estimation des POIs (environ 40% sont de vrais POIs)
            estimated_pois = int(total_urls * 0.4)
            
            # Calcul des coûts
            scrapingbee_cost = 0  # Gratuit jusqu'à 1000/mois
            if total_urls > 1000:
                scrapingbee_cost = (total_urls - 1000) * 0.01  # 1 cent par URL extra
                
            openai_cost = total_urls * self.cost_per_url
            total_cost = scrapingbee_cost + openai_cost
            
            # Temps estimé
            time_per_url = 15  # secondes
            total_time_minutes = (total_urls * time_per_url) / 60
            
            estimation = {
                'url_breakdown': url_counts,
                'total_urls': total_urls,
                'estimated_pois': estimated_pois,
                'costs': {
                    'scrapingbee': f"${scrapingbee_cost:.2f}",
                    'openai': f"${openai_cost:.2f}",
                    'total': f"${total_cost:.2f}"
                },
                'estimated_time': f"{total_time_minutes:.0f} minutes",
                'mode': self.quality_mode,
                'cost_per_poi': f"${total_cost/estimated_pois:.2f}" if estimated_pois > 0 else "N/A"
            }
            
            return estimation
            
        except Exception as e:
            logger.error(f"Erreur lors de l'estimation: {str(e)}")
            return {'error': str(e)}
            
    def log_to_database(self, status: str, message: str, details: Optional[Dict] = None):
        """Enregistre un log dans la table agent_logs"""
        try:
            log_entry = {
                'agent_name': self.agent_name,
                'status': status,
                'message': message,
                'details': details or {}
            }
            
            self.supabase.table('agent_logs').insert(log_entry).execute()
            logger.info(f"📝 Log DB: {status} - {message}")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'écriture du log en DB: {str(e)}")
            
    def fetch_sitemap_urls_by_priority(self, priority='high') -> List[str]:
        """Récupère les URLs selon la priorité choisie"""
        all_urls = []
        sitemaps = []
        
        if priority == 'all':
            for prio in ['high', 'medium', 'low']:
                sitemaps.extend(self.PRIORITY_SITEMAPS[prio])
        else:
            sitemaps = self.PRIORITY_SITEMAPS.get(priority, [])
            
        for sitemap_url in sitemaps:
            try:
                logger.info(f"📥 Téléchargement du sitemap: {sitemap_url}")
                response = requests.get(sitemap_url, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'xml')
                urls = [loc.text for loc in soup.find_all('loc')]
                
                logger.info(f"✅ {len(urls)} URLs trouvées dans {sitemap_url}")
                all_urls.extend(urls)
                
            except Exception as e:
                logger.error(f"❌ Erreur pour {sitemap_url}: {str(e)}")
                continue
                
        # Dédupliquer
        all_urls = list(set(all_urls))
        logger.info(f"📊 Total: {len(all_urls)} URLs uniques (priorité: {priority})")
        
        return all_urls
            
    def get_processed_urls(self) -> set:
        """Récupère la liste des URLs déjà traitées depuis la DB"""
        try:
            response = self.supabase.table('processed_urls').select('url').execute()
            processed_urls = {row['url'] for row in response.data}
            
            logger.info(f"📊 {len(processed_urls)} URLs déjà traitées en base")
            return processed_urls
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des URLs traitées: {str(e)}")
            return set()
            
    def download_page_content(self, url: str) -> str:
        """Télécharge le contenu HTML d'une page via ScrapingBee"""
        try:
            params = {
                'api_key': self.scrapingbee_api_key,
                'url': url,
                'render_js': 'false',
                'block_resources': 'true',
                'premium_proxy': 'false'
            }
            
            response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=60)
            response.raise_for_status()
            
            return response.text
            
        except Exception as e:
            logger.error(f"❌ Erreur ScrapingBee pour {url}: {str(e)}")
            raise
            
    def extract_text_content(self, html: str) -> str:
        """Extrait le texte principal d'une page HTML Tokyo Cheapo"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Suppression des éléments non pertinents
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
                
            # Structure spécifique Tokyo Cheapo
            # 1. Chercher le contenu principal avec les bonnes classes
            main_content = (
                soup.find('div', class_='entry-content') or 
                soup.find('article') or 
                soup.find('main') or
                soup.find('div', class_='article')
            )
            
            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)
                
            # Nettoyage
            text = ' '.join(text.split())
            
            # Limitation pour les APIs
            if len(text) > 10000:
                text = text[:10000] + "..."
                
            return text
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'extraction du texte: {str(e)}")
            raise
            
    def classify_as_poi(self, text: str) -> Tuple[bool, str]:
        """Classification intelligente avec catégorisation"""
        try:
            prompt = """Tu es un expert en voyage à Tokyo.
Analyse ce texte et détermine:
1. Est-ce un lieu physique unique et visitable à Tokyo ? (OUI/NON)
2. Si OUI, quelle catégorie : RESTAURANT, ATTRACTION, HOTEL, SHOPPING, TEMPLE, MUSEE, PARC, BAR, CAFE, AUTRE

Réponds UNIQUEMENT au format JSON: {"is_poi": true/false, "category": "CATEGORIE"}"""
            
            response = self.openai_client.chat.completions.create(
                model=self.classification_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text[:2500]}
                ],
                temperature=0.3,
                max_tokens=50
            )
            
            try:
                result = json.loads(response.choices[0].message.content)
                is_poi = result.get('is_poi', False)
                category = result.get('category', 'AUTRE')
            except:
                # Fallback si pas de JSON valide
                answer = response.choices[0].message.content.upper()
                is_poi = 'OUI' in answer or 'TRUE' in answer
                category = 'AUTRE'
                
            # Coût
            if self.classification_model == "gpt-4-turbo-preview":
                self.total_cost_estimate += 0.03
            else:
                self.total_cost_estimate += 0.002
                
            return is_poi, category
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la classification: {str(e)}")
            return False, 'UNKNOWN'
            
    def generate_quality_description(self, text: str, category: str) -> str:
        """Génère une description de qualité selon le mode"""
        try:
            # Prompts adaptés par catégorie
            if category == 'RESTAURANT':
                style = "culinaire et appétissant"
            elif category in ['TEMPLE', 'MUSEE']:
                style = "culturel et respectueux"
            elif category == 'ATTRACTION':
                style = "captivant et informatif"
            else:
                style = "engageant et descriptif"
                
            prompt = f"""Tu es un rédacteur expert de guides de voyage, spécialiste de Tokyo.
Crée une description {style} de ce lieu en 150-200 mots.
La description doit être 100% originale, captivante et donner envie de visiter.
Ne copie AUCUNE phrase du texte source."""
            
            response = self.openai_client.chat.completions.create(
                model=self.generation_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text[:3500]}
                ],
                temperature=0.8,
                max_tokens=400,
                presence_penalty=0.5
            )
            
            description = response.choices[0].message.content.strip()
            
            # Coût
            if self.generation_model == "gpt-4-turbo-preview":
                self.total_cost_estimate += 0.04
            else:
                self.total_cost_estimate += 0.004
                
            return description
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération: {str(e)}")
            raise
            
    def extract_structured_data(self, text: str, description: str, category: str) -> Dict[str, Any]:
        """Extraction de données structurées"""
        try:
            prompt = """Extrais les informations suivantes au format JSON.
Si une information est introuvable, retourne null.

{
  "name": "Nom du lieu",
  "neighborhood": "Quartier de Tokyo",
  "summary": "Résumé en 1 phrase (max 100 char)",
  "keywords": ["5-8 mots-clés pertinents"],
  "price_range": "¥ à ¥¥¥¥¥ ou null"
}"""
            
            context = f"Catégorie: {category}\nDescription: {description}\nTexte source: {text[:1500]}"
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # Toujours 3.5 pour l'extraction
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            try:
                extracted = json.loads(response.choices[0].message.content)
            except:
                extracted = {"name": None, "summary": None, "keywords": []}
                
            self.total_cost_estimate += 0.003
            
            return extracted
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'extraction: {str(e)}")
            return {"name": None, "summary": None, "keywords": []}
            
    def get_embedding(self, text: str) -> List[float]:
        """Génère un embedding pour le texte"""
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=text[:8000]
            )
            
            self.total_cost_estimate += 0.0004
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération d'embedding: {str(e)}")
            raise
            
    def check_semantic_duplicate(self, embedding: List[float], threshold: float = 0.9) -> bool:
        """Vérifie si un POI similaire existe déjà"""
        try:
            response = self.supabase.rpc(
                'match_locations',
                {
                    'query_embedding': embedding,
                    'match_threshold': threshold,
                    'match_count': 1
                }
            ).execute()
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de la vérification de doublon: {str(e)}")
            return False
            
    def save_poi_to_database(self, poi_data: Dict[str, Any], url: str, category: str) -> bool:
        """Sauvegarde un POI dans la base de données"""
        try:
            location_data = {
                'name': poi_data['name'] or "POI sans nom",
                'description': poi_data['description'],
                'summary': poi_data.get('summary'),
                'category': category,
                'neighborhood': poi_data.get('neighborhood'),
                'is_active': False,
                'source_url': url,
                'source_name': self.site_name,
                'source_scraped_at': datetime.utcnow().isoformat(),
                'embedding': poi_data.get('embedding'),
                'features': {
                    'keywords': poi_data.get('keywords', []),
                    'price_range': poi_data.get('price_range'),
                    'quality_mode': self.quality_mode
                }
            }
            
            self.supabase.table('locations').insert(location_data).execute()
            
            logger.info(f"✅ POI créé: {poi_data['name']} ({category})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde: {str(e)}")
            raise
            
    def mark_url_as_processed(self, url: str, status: str):
        """Marque une URL comme traitée"""
        try:
            self.supabase.table('processed_urls').insert({
                'url': url,
                'status': status
            }).execute()
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du marquage de l'URL: {str(e)}")
            
    def process_single_url(self, url: str) -> str:
        """Traite une URL unique avec stratégie smart"""
        try:
            logger.info(f"🔄 Traitement de: {url}")
            
            # Étape 1: Téléchargement
            html_content = self.download_page_content(url)
            text_content = self.extract_text_content(html_content)
            
            if len(text_content) < 200:
                logger.warning(f"⚠️ Contenu trop court pour {url}")
                return 'skipped_not_a_poi'
                
            # Étape 2: Classification (toujours avec le modèle configuré)
            is_poi, category = self.classify_as_poi(text_content)
            
            if not is_poi:
                logger.info(f"ℹ️ {url} n'est pas un POI")
                return 'skipped_not_a_poi'
                
            logger.info(f"✅ POI détecté - Catégorie: {category}")
            
            # Étape 3: Génération de description (avec le bon modèle selon mode)
            description = self.generate_quality_description(text_content, category)
            
            # Étape 4: Extraction structurée
            structured_data = self.extract_structured_data(text_content, description, category)
            
            # Étape 5: Embedding
            embedding = self.get_embedding(description)
            
            # Étape 6: Vérification doublon
            is_duplicate = self.check_semantic_duplicate(embedding)
            
            if is_duplicate:
                logger.info(f"ℹ️ Doublon détecté pour {url}")
                return 'skipped_duplicate'
                
            # Étape 7: Sauvegarde
            poi_data = {
                **structured_data,
                'description': description,
                'embedding': embedding
            }
            
            self.save_poi_to_database(poi_data, url, category)
            
            return 'success'
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du traitement de {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return 'failed'
            
    def run(self, priority='high', dry_run=False):
        """
        Méthode principale d'exécution
        
        Args:
            priority: 'high', 'medium', 'low', ou 'all'
            dry_run: Si True, affiche seulement l'estimation sans crawler
        """
        try:
            # Vérification du schéma
            logger.info("🔍 Vérification du schéma de base de données...")
            schema_check = self.verify_database_schema()
            
            if not all(schema_check.values()):
                logger.error("❌ Le schéma de base de données n'est pas complet!")
                logger.error("Exécutez d'abord le script database_setup.sql dans Supabase")
                return
                
            # Estimation des coûts
            logger.info(f"💰 Estimation des coûts (mode: {self.quality_mode}, priorité: {priority})...")
            estimation = self.estimate_costs(priority)
            
            print("\n" + "="*60)
            print("📊 ESTIMATION DU CRAWL")
            print("="*60)
            print(f"Mode de qualité: {self.quality_mode.upper()}")
            print(f"Priorité: {priority}")
            print(f"URLs à traiter: {estimation['total_urls']}")
            print(f"POIs estimés: {estimation['estimated_pois']}")
            print(f"Temps estimé: {estimation['estimated_time']}")
            print(f"Coût total estimé: {estimation['costs']['total']}")
            print(f"Coût par POI: {estimation['cost_per_poi']}")
            print("="*60 + "\n")
            
            if dry_run:
                logger.info("Mode DRY RUN - Arrêt ici")
                return
                
            # Confirmation
            if estimation['total_urls'] > 100:
                confirm = input(f"⚠️  Voulez-vous vraiment crawler {estimation['total_urls']} URLs? (oui/non): ")
                if confirm.lower() != 'oui':
                    logger.info("Crawl annulé")
                    return
                    
            # Log de démarrage
            self.log_to_database(
                'STARTED',
                f'Lancement du crawl SMART (mode: {self.quality_mode}, priorité: {priority})',
                estimation
            )
            
            # Récupération des URLs
            logger.info("🚀 Démarrage du crawler intelligent")
            all_urls = self.fetch_sitemap_urls_by_priority(priority)
            processed_urls = self.get_processed_urls()
            
            # URLs à traiter
            urls_to_process = [url for url in all_urls if url not in processed_urls]
            
            if not urls_to_process:
                message = "Aucune nouvelle URL à traiter."
                logger.info(f"✅ {message}")
                self.log_to_database('SUCCESS', message)
                return
                
            logger.info(f"📋 {len(urls_to_process)} nouvelles URLs à traiter")
            
            # Boucle de traitement
            start_time = time.time()
            
            for idx, url in enumerate(urls_to_process, 1):
                try:
                    # Traitement
                    status = self.process_single_url(url)
                    
                    # Mise à jour des compteurs
                    self.processed_count += 1
                    if status == 'success':
                        self.success_count += 1
                    elif status in ['skipped_not_a_poi', 'skipped_duplicate']:
                        self.skip_count += 1
                    else:
                        self.error_count += 1
                        
                    # Enregistrement
                    self.mark_url_as_processed(url, status)
                    
                    # Log de progression
                    if self.processed_count % self.batch_log_interval == 0:
                        elapsed = time.time() - start_time
                        rate = self.processed_count / (elapsed / 60)
                        
                        progress_msg = (
                            f"Progression: {self.processed_count}/{len(urls_to_process)} - "
                            f"✅ {self.success_count} POIs, "
                            f"⏭️ {self.skip_count} ignorés, "
                            f"❌ {self.error_count} erreurs - "
                            f"Vitesse: {rate:.1f} URLs/min - "
                            f"Coût: ${self.total_cost_estimate:.2f}"
                        )
                        logger.info(progress_msg)
                        self.log_to_database('RUNNING', progress_msg)
                        
                    # Délai
                    time.sleep(self.delay_between_urls)
                    
                except Exception as e:
                    logger.error(f"❌ Erreur non gérée pour {url}: {str(e)}")
                    self.error_count += 1
                    self.mark_url_as_processed(url, 'failed')
                    continue
                    
            # Log final
            duration = time.time() - start_time
            final_message = (
                f"Scan terminé! Total: {self.processed_count}, "
                f"POIs créés: {self.success_count}, "
                f"Ignorés: {self.skip_count}, "
                f"Erreurs: {self.error_count} - "
                f"Durée: {duration/60:.1f} min - "
                f"Coût total: ${self.total_cost_estimate:.2f}"
            )
            
            logger.info(f"🎉 {final_message}")
            self.log_to_database('SUCCESS', final_message, {
                'total_processed': self.processed_count,
                'success': self.success_count,
                'skipped': self.skip_count,
                'errors': self.error_count,
                'duration_seconds': duration,
                'total_cost': self.total_cost_estimate
            })
            
        except Exception as e:
            error_msg = f"Erreur fatale: {str(e)}"
            logger.error(f"💥 {error_msg}")
            logger.error(traceback.format_exc())
            self.log_to_database('ERROR', error_msg)
            raise


def main():
    """Point d'entrée avec options de ligne de commande"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Yorimichi Smart Crawler')
    parser.add_argument(
        '--mode', 
        choices=['smart', 'premium', 'economy'], 
        default='smart',
        help='Mode de qualité (smart recommandé)'
    )
    parser.add_argument(
        '--priority',
        choices=['high', 'medium', 'low', 'all'],
        default='high',
        help='Priorité des sitemaps à crawler'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Affiche seulement l\'estimation sans crawler'
    )
    
    args = parser.parse_args()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║           YORIMICHI SMART CRAWLER - Version 3.0              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        crawler = YorimichiSmartCrawler(quality_mode=args.mode)
        crawler.run(priority=args.priority, dry_run=args.dry_run)
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ Arrêt manuel du crawler")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Erreur fatale: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()