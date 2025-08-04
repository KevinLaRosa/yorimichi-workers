#!/usr/bin/env python3
"""
Worker Intelligent Yorimichi V2
Agent de collecte de contenu intelligent pour le crawling, la reformulation et l'extraction de POI
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
        logging.FileHandler('yorimichi_crawler.log')
    ]
)
logger = logging.getLogger('YorimichiCrawler')


class YorimichiIntelligentCrawler:
    """Agent intelligent de collecte et transformation de contenu POI"""
    
    def __init__(self):
        """Initialisation du crawler avec chargement des configurations"""
        # Charger les variables d'environnement (priorité: .env.local > .env)
        if os.path.exists('.env.local'):
            load_dotenv('.env.local')
        else:
            load_dotenv()
        
        # Validation des variables d'environnement
        self.validate_environment()
        
        # Initialisation des clients
        self.supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_SERVICE_KEY')
        )
        
        # Configuration OpenAI
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Configuration ScrapingBee
        self.scrapingbee_api_key = os.getenv('SCRAPINGBEE_API_KEY')
        
        # Paramètres de configuration
        self.site_name = "Tokyo Cheapo"
        self.sitemap_url = "https://tokyocheapo.com/post-sitemap.xml"
        self.agent_name = "Intelligent Crawler V2"
        self.batch_log_interval = 25
        self.delay_between_urls = 1
        
        # Compteurs pour le suivi
        self.processed_count = 0
        self.success_count = 0
        self.skip_count = 0
        self.error_count = 0
        
    def validate_environment(self):
        """Valide que toutes les variables d'environnement requises sont présentes"""
        required_vars = [
            'SUPABASE_URL',
            'SUPABASE_SERVICE_KEY',
            'OPENAI_API_KEY',
            'SCRAPINGBEE_API_KEY'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            error_msg = f"Variables d'environnement manquantes: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise EnvironmentError(error_msg)
            
        logger.info("✅ Toutes les variables d'environnement sont configurées")
        
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
            
    def fetch_sitemap_urls(self) -> List[str]:
        """Récupère toutes les URLs depuis le sitemap"""
        try:
            logger.info(f"📥 Téléchargement du sitemap: {self.sitemap_url}")
            
            response = requests.get(self.sitemap_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            urls = [loc.text for loc in soup.find_all('loc')]
            
            logger.info(f"✅ {len(urls)} URLs trouvées dans le sitemap")
            return urls
            
        except Exception as e:
            error_msg = f"Erreur lors du téléchargement du sitemap: {str(e)}"
            logger.error(error_msg)
            self.log_to_database('ERROR', error_msg)
            raise
            
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
        """Extrait le texte principal d'une page HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Suppression des éléments non pertinents
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
                
            # Extraction du contenu principal
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
            
            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)
                
            # Nettoyage du texte
            text = ' '.join(text.split())
            
            # Limitation de la taille pour les API
            if len(text) > 10000:
                text = text[:10000] + "..."
                
            return text
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'extraction du texte: {str(e)}")
            raise
            
    def classify_as_poi(self, text: str) -> bool:
        """Utilise GPT-3.5 pour déterminer si le texte décrit un POI"""
        try:
            prompt = (
                "Tu es un assistant de voyage spécialisé sur Tokyo. "
                "Ce texte décrit-il un lieu physique unique et visitable à Tokyo ? "
                "Réponds uniquement par OUI ou NON."
            )
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text[:2000]}  # Limite pour économiser les tokens
                ],
                temperature=0.3,
                max_tokens=10
            )
            
            answer = response.choices[0].message.content.strip().upper()
            return answer == "OUI"
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la classification: {str(e)}")
            raise
            
    def rewrite_content(self, text: str) -> str:
        """Utilise GPT-4 pour reformuler le contenu de manière unique"""
        try:
            prompt = (
                "Tu es un rédacteur de guides de voyage au style 'lovely' et poétique. "
                "En te basant sur le texte suivant, rédige une description 100% unique et originale "
                "qui capture l'ambiance et l'émotion du lieu. Ne copie aucune phrase."
            )
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text[:3000]}  # Limite pour optimiser les coûts
                ],
                temperature=0.8,
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la reformulation: {str(e)}")
            raise
            
    def extract_structured_data(self, text: str) -> Dict[str, Any]:
        """Utilise GPT-4 pour extraire les données structurées"""
        try:
            prompt = (
                "En te basant sur le texte suivant, extrais les informations ci-dessous au format JSON. "
                "Si une information est introuvable, retourne null.\n"
                '{ "name": string, "neighborhood": string, "summary": string, "keywords": string[] }'
            )
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            # Extraction et parsing du JSON
            json_str = response.choices[0].message.content.strip()
            # Nettoyage au cas où le modèle ajoute des backticks
            json_str = json_str.replace('```json', '').replace('```', '').strip()
            
            return json.loads(json_str)
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erreur de parsing JSON: {str(e)}")
            return {"name": None, "neighborhood": None, "summary": None, "keywords": []}
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'extraction structurée: {str(e)}")
            raise
            
    def get_embedding(self, text: str) -> List[float]:
        """Génère un embedding pour le texte donné"""
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=text[:8000]  # Limite de tokens pour le modèle
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération d'embedding: {str(e)}")
            raise
            
    def check_semantic_duplicate(self, embedding: List[float], threshold: float = 0.9) -> bool:
        """Vérifie si un POI similaire existe déjà en base"""
        try:
            # Appel de la fonction RPC Supabase pour la recherche vectorielle
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
            # En cas d'erreur, on continue (on ne veut pas bloquer le processus)
            return False
            
    def save_poi_to_database(self, poi_data: Dict[str, Any], url: str) -> bool:
        """Sauvegarde un POI dans la base de données"""
        try:
            # Préparation des données pour l'insertion
            location_data = {
                'name': poi_data['name'] or "POI sans nom",
                'description': poi_data['description'],
                'is_active': False,  # Brouillon par défaut
                'source_url': url,
                'source_name': self.site_name,
                'source_scraped_at': datetime.utcnow().isoformat(),
                'features': {
                    'neighborhood': poi_data.get('neighborhood'),
                    'keywords': poi_data.get('keywords', []),
                    'summary': poi_data.get('summary')
                }
            }
            
            # Insertion dans la table locations
            self.supabase.table('locations').insert(location_data).execute()
            
            logger.info(f"✅ POI créé: {poi_data['name']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde du POI: {str(e)}")
            raise
            
    def mark_url_as_processed(self, url: str, status: str):
        """Marque une URL comme traitée dans la base de données"""
        try:
            self.supabase.table('processed_urls').insert({
                'url': url,
                'status': status
            }).execute()
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du marquage de l'URL: {str(e)}")
            
    def process_single_url(self, url: str) -> str:
        """Traite une URL unique et retourne son statut"""
        try:
            logger.info(f"🔄 Traitement de: {url}")
            
            # Étape 1: Téléchargement du contenu
            html_content = self.download_page_content(url)
            text_content = self.extract_text_content(html_content)
            
            if len(text_content) < 100:
                logger.warning(f"⚠️ Contenu trop court pour {url}")
                return 'skipped_not_a_poi'
                
            # Étape 2: Classification
            is_poi = self.classify_as_poi(text_content)
            
            if not is_poi:
                logger.info(f"ℹ️ {url} n'est pas un POI")
                return 'skipped_not_a_poi'
                
            # Étape 3: Reformulation
            lovely_description = self.rewrite_content(text_content)
            
            # Étape 4: Extraction structurée
            structured_data = self.extract_structured_data(lovely_description)
            
            # Étape 5: Vérification de doublon
            embedding = self.get_embedding(lovely_description)
            is_duplicate = self.check_semantic_duplicate(embedding)
            
            if is_duplicate:
                logger.info(f"ℹ️ Doublon détecté pour {url}")
                return 'skipped_duplicate'
                
            # Étape 6: Sauvegarde
            poi_data = {
                **structured_data,
                'description': lovely_description
            }
            
            self.save_poi_to_database(poi_data, url)
            
            return 'success'
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du traitement de {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return 'failed'
            
    def run(self):
        """Méthode principale d'exécution du crawler"""
        try:
            # Log de démarrage
            self.log_to_database(
                'STARTED',
                f'Lancement du scan complet pour {self.site_name}',
                {'sitemap_url': self.sitemap_url}
            )
            
            # Récupération des URLs
            logger.info("🚀 Démarrage du crawler intelligent Yorimichi")
            all_urls = self.fetch_sitemap_urls()
            processed_urls = self.get_processed_urls()
            
            # Calcul des URLs à traiter
            urls_to_process = [url for url in all_urls if url not in processed_urls]
            
            if not urls_to_process:
                message = "Aucune nouvelle URL à traiter."
                logger.info(f"✅ {message}")
                self.log_to_database('SUCCESS', message)
                return
                
            logger.info(f"📋 {len(urls_to_process)} nouvelles URLs à traiter")
            
            # Boucle de traitement principale
            for idx, url in enumerate(urls_to_process, 1):
                try:
                    # Traitement de l'URL
                    status = self.process_single_url(url)
                    
                    # Mise à jour des compteurs
                    self.processed_count += 1
                    if status == 'success':
                        self.success_count += 1
                    elif status in ['skipped_not_a_poi', 'skipped_duplicate']:
                        self.skip_count += 1
                    else:
                        self.error_count += 1
                        
                    # Enregistrement du statut
                    self.mark_url_as_processed(url, status)
                    
                    # Log de progression
                    if self.processed_count % self.batch_log_interval == 0:
                        progress_msg = (
                            f"Progression: {self.processed_count}/{len(urls_to_process)} URLs - "
                            f"✅ {self.success_count} POIs créés, "
                            f"⏭️ {self.skip_count} ignorés, "
                            f"❌ {self.error_count} erreurs"
                        )
                        logger.info(progress_msg)
                        self.log_to_database('RUNNING', progress_msg, {
                            'processed': self.processed_count,
                            'total': len(urls_to_process),
                            'success': self.success_count,
                            'skipped': self.skip_count,
                            'errors': self.error_count
                        })
                        
                    # Délai entre les requêtes
                    time.sleep(self.delay_between_urls)
                    
                except Exception as e:
                    logger.error(f"❌ Erreur non gérée pour {url}: {str(e)}")
                    self.error_count += 1
                    self.mark_url_as_processed(url, 'failed')
                    self.log_to_database('ERROR', f"Erreur sur {url}", {'error': str(e)})
                    continue
                    
            # Log de fin
            final_message = (
                f"Scan terminé avec succès! "
                f"Total traité: {self.processed_count}, "
                f"POIs créés: {self.success_count}, "
                f"Ignorés: {self.skip_count}, "
                f"Erreurs: {self.error_count}"
            )
            
            logger.info(f"🎉 {final_message}")
            self.log_to_database('SUCCESS', final_message, {
                'total_processed': self.processed_count,
                'success': self.success_count,
                'skipped': self.skip_count,
                'errors': self.error_count,
                'duration_seconds': time.time()
            })
            
        except Exception as e:
            error_msg = f"Erreur fatale du crawler: {str(e)}"
            logger.error(f"💥 {error_msg}")
            logger.error(traceback.format_exc())
            self.log_to_database('ERROR', error_msg, {'traceback': traceback.format_exc()})
            raise


def main():
    """Point d'entrée principal du script"""
    try:
        crawler = YorimichiIntelligentCrawler()
        crawler.run()
    except KeyboardInterrupt:
        logger.info("\n⏹️ Arrêt manuel du crawler")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Erreur fatale: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()