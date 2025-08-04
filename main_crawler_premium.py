#!/usr/bin/env python3
"""
Worker Intelligent Yorimichi V2 - PREMIUM QUALITY EDITION
Version optimisée pour la meilleure qualité de contenu possible
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
        logging.FileHandler('yorimichi_crawler_premium.log')
    ]
)
logger = logging.getLogger('YorimichiPremiumCrawler')


class YorimichiPremiumCrawler:
    """Agent premium de collecte avec focus sur la qualité maximale"""
    
    # Tous les sitemaps de Tokyo Cheapo à crawler
    TOKYO_CHEAPO_SITEMAPS = [
        "https://tokyocheapo.com/place-sitemap1.xml",
        "https://tokyocheapo.com/place-sitemap2.xml",
        "https://tokyocheapo.com/place-sitemap3.xml",
        "https://tokyocheapo.com/restaurant-sitemap1.xml",
        "https://tokyocheapo.com/restaurant-sitemap2.xml",
        "https://tokyocheapo.com/accommodation-sitemap.xml",
        "https://tokyocheapo.com/event-sitemap1.xml",
        "https://tokyocheapo.com/event-sitemap2.xml",
        "https://tokyocheapo.com/tour-sitemap.xml",
    ]
    
    def __init__(self):
        """Initialisation du crawler premium avec configuration de qualité"""
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
        
        # Configuration OpenAI avec modèles premium
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Configuration ScrapingBee
        self.scrapingbee_api_key = os.getenv('SCRAPINGBEE_API_KEY')
        
        # Paramètres de configuration PREMIUM
        self.site_name = "Tokyo Cheapo"
        self.agent_name = "Premium Intelligent Crawler V2"
        self.batch_log_interval = 10
        self.delay_between_urls = 2  # Plus de délai pour éviter rate limits
        
        # Modèles GPT premium
        self.classification_model = "gpt-4-turbo-preview"  # GPT-4 même pour classification
        self.generation_model = "gpt-4-turbo-preview"
        self.embedding_model = "text-embedding-3-large"  # Meilleur modèle d'embedding
        
        # Compteurs pour le suivi
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
            
    def fetch_all_sitemap_urls(self) -> List[str]:
        """Récupère TOUTES les URLs depuis TOUS les sitemaps Tokyo Cheapo"""
        all_urls = []
        
        for sitemap_url in self.TOKYO_CHEAPO_SITEMAPS:
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
                
        # Dédupliquer au cas où
        all_urls = list(set(all_urls))
        logger.info(f"📊 Total: {len(all_urls)} URLs uniques trouvées")
        
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
        """Télécharge le contenu HTML d'une page via ScrapingBee avec options premium"""
        try:
            params = {
                'api_key': self.scrapingbee_api_key,
                'url': url,
                'render_js': 'false',
                'block_resources': 'false',  # On veut tout le contenu
                'premium_proxy': 'true',  # Proxy premium pour meilleure fiabilité
                'country_code': 'jp'  # Depuis le Japon pour contenu local
            }
            
            response = requests.get('https://app.scrapingbee.com/api/v1/', params=params, timeout=60)
            response.raise_for_status()
            
            return response.text
            
        except Exception as e:
            logger.error(f"❌ Erreur ScrapingBee pour {url}: {str(e)}")
            raise
            
    def extract_rich_content(self, html: str, url: str) -> Dict[str, Any]:
        """Extraction enrichie du contenu avec métadonnées"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extraction enrichie avec plus de contexte
            content = {
                'text': '',
                'title': '',
                'meta_description': '',
                'images': [],
                'categories': [],
                'tags': [],
                'address': None,
                'opening_hours': None,
                'price_info': None
            }
            
            # Titre
            title_tag = soup.find('h1') or soup.find('title')
            if title_tag:
                content['title'] = title_tag.get_text(strip=True)
                
            # Meta description
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc:
                content['meta_description'] = meta_desc.get('content', '')
                
            # Images principales
            images = soup.find_all('img', limit=5)
            content['images'] = [img.get('src', '') for img in images if img.get('src')]
            
            # Catégories et tags
            categories = soup.find_all(['a'], {'rel': 'category tag'})
            content['categories'] = [cat.get_text(strip=True) for cat in categories]
            
            tags = soup.find_all(['a'], {'rel': 'tag'})
            content['tags'] = [tag.get_text(strip=True) for tag in tags]
            
            # Contenu principal avec structure préservée
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
            
            if main_content:
                # Garder les titres pour la structure
                for tag in ['h2', 'h3', 'h4']:
                    for header in main_content.find_all(tag):
                        header.string = f"\n\n[{tag.upper()}] {header.get_text(strip=True)}\n"
                        
                # Extraire le texte structuré
                content['text'] = main_content.get_text(separator=' ', strip=True)
            else:
                content['text'] = soup.get_text(separator=' ', strip=True)
                
            # Nettoyage mais en gardant la richesse
            content['text'] = ' '.join(content['text'].split())
            
            # Informations spécifiques si détectables
            address_elem = soup.find(['address', 'div'], class_=['address', 'location'])
            if address_elem:
                content['address'] = address_elem.get_text(strip=True)
                
            # Prix
            price_elems = soup.find_all(text=lambda t: '¥' in t or 'yen' in t.lower())
            if price_elems:
                content['price_info'] = ' | '.join([p.strip() for p in price_elems[:3]])
                
            return content
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'extraction enrichie: {str(e)}")
            raise
            
    def classify_as_poi_premium(self, content: Dict[str, Any]) -> Tuple[bool, str]:
        """Classification premium avec catégorisation"""
        try:
            # Prompt amélioré pour classification ET catégorisation
            prompt = """Tu es un expert en voyage à Tokyo avec 10 ans d'expérience.
            
Analyse ce contenu et détermine:
1. Est-ce un lieu physique unique et visitable à Tokyo ? (OUI/NON)
2. Si OUI, quelle catégorie principale : RESTAURANT, ATTRACTION, HOTEL, SHOPPING, TEMPLE, MUSEE, PARC, BAR, CAFE, AUTRE

Réponds au format JSON: {"is_poi": true/false, "category": "CATEGORIE"}

IMPORTANT: Un article de blog général ou un guide n'est PAS un POI."""
            
            # Contexte enrichi pour la classification
            context_text = f"""
Titre: {content['title']}
Description: {content['meta_description']}
Catégories: {', '.join(content['categories'])}
Contenu: {content['text'][:3000]}
"""
            
            response = self.openai_client.chat.completions.create(
                model=self.classification_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context_text}
                ],
                temperature=0.1,  # Très faible pour cohérence
                max_tokens=50,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Estimation du coût
            self.total_cost_estimate += 0.03  # GPT-4 classification
            
            return result.get('is_poi', False), result.get('category', 'AUTRE')
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la classification premium: {str(e)}")
            return False, 'UNKNOWN'
            
    def generate_premium_description(self, content: Dict[str, Any], category: str) -> str:
        """Génération de description premium adaptée à la catégorie"""
        try:
            # Prompts spécialisés par catégorie
            category_prompts = {
                'RESTAURANT': """Tu es Anthony Bourdain réincarné, expert culinaire passionné par Tokyo.
Crée une description qui capture l'essence de ce restaurant : l'ambiance, les saveurs signature, 
l'expérience unique. Évoque les émotions, les parfums, la magie du lieu.
Style: Poétique mais authentique, 150-200 mots.""",
                
                'ATTRACTION': """Tu es un guide culturel expert de Tokyo depuis 20 ans.
Décris cette attraction en capturant son essence unique, son importance culturelle,
et pourquoi elle mérite d'être visitée. Transmets l'émerveillement.
Style: Inspirant et informatif, 150-200 mots.""",
                
                'TEMPLE': """Tu es un expert en culture japonaise et spiritualité.
Décris ce temple en évoquant sa sérénité, son histoire, son architecture.
Aide le lecteur à ressentir la paix et la beauté sacrée du lieu.
Style: Respectueux et contemplatif, 150-200 mots.""",
                
                'DEFAULT': """Tu es un écrivain de guides de voyage primé, spécialiste de Tokyo.
Crée une description captivante et unique de ce lieu. Évoque les sensations,
l'atmosphère, ce qui rend cet endroit spécial et mémorable.
Style: Engageant et évocateur, 150-200 mots."""
            }
            
            prompt = category_prompts.get(category, category_prompts['DEFAULT'])
            
            # Contexte enrichi pour la génération
            enriched_context = f"""
Titre: {content['title']}
Catégorie: {category}
Adresse: {content['address'] or 'Non spécifiée'}
Prix: {content['price_info'] or 'Non spécifié'}
Tags: {', '.join(content['tags'])}

Contenu source:
{content['text'][:4000]}

CONSIGNES CRITIQUES:
- Ne JAMAIS copier de phrases du texte source
- Créer une description 100% originale et unique
- Capturer l'essence émotionnelle du lieu
- Utiliser un vocabulaire riche et évocateur
- Rester authentique et crédible
"""
            
            response = self.openai_client.chat.completions.create(
                model=self.generation_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": enriched_context}
                ],
                temperature=0.85,  # Créativité élevée
                max_tokens=400,
                presence_penalty=0.6,  # Éviter les répétitions
                frequency_penalty=0.4
            )
            
            description = response.choices[0].message.content.strip()
            
            # Estimation du coût
            self.total_cost_estimate += 0.04  # GPT-4 génération
            
            return description
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération premium: {str(e)}")
            raise
            
    def extract_structured_data_premium(self, content: Dict[str, Any], description: str, category: str) -> Dict[str, Any]:
        """Extraction de données structurées enrichies"""
        try:
            prompt = f"""En tant qu'expert data analyst spécialisé dans le tourisme à Tokyo,
extrais les informations structurées suivantes au format JSON.

Catégorie du lieu: {category}

Si une information est introuvable, retourne null. Sois précis et factuel.

{{
  "name": "Nom officiel du lieu",
  "name_jp": "Nom en japonais si disponible",
  "neighborhood": "Quartier de Tokyo",
  "district": "Arrondissement (ex: Shibuya-ku)",
  "summary": "Résumé factuel en 1 phrase (max 100 caractères)",
  "keywords": ["5-8 mots-clés pertinents"],
  "price_range": "¥ à ¥¥¥¥¥ ou null",
  "best_for": ["couples", "familles", "solo", "groupes", etc.],
  "highlights": ["3-5 points forts uniques"],
  "practical_info": {{
    "nearest_station": "Station la plus proche",
    "walking_time": "Temps de marche depuis la station",
    "best_time_to_visit": "Meilleur moment pour visiter"
  }}
}}"""
            
            # Contexte complet pour l'extraction
            full_context = f"""
Description générée: {description}

Informations source:
Titre: {content['title']}
Adresse: {content['address']}
Prix: {content['price_info']}
Catégories: {', '.join(content['categories'])}
Tags: {', '.join(content['tags'])}

Texte original (extrait):
{content['text'][:2000]}
"""
            
            response = self.openai_client.chat.completions.create(
                model=self.generation_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": full_context}
                ],
                temperature=0.2,  # Précision pour l'extraction
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            extracted_data = json.loads(response.choices[0].message.content)
            
            # Estimation du coût
            self.total_cost_estimate += 0.03  # GPT-4 extraction
            
            return extracted_data
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erreur de parsing JSON: {str(e)}")
            return {"name": content['title'], "summary": None, "keywords": []}
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'extraction premium: {str(e)}")
            raise
            
    def get_premium_embedding(self, text: str) -> List[float]:
        """Génère un embedding de haute qualité pour le texte"""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text[:8000]
            )
            
            # Estimation du coût
            self.total_cost_estimate += 0.0013  # Embedding large model
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération d'embedding: {str(e)}")
            raise
            
    def check_semantic_duplicate(self, embedding: List[float], threshold: float = 0.92) -> bool:
        """Vérifie les doublons avec seuil plus strict pour qualité"""
        try:
            response = self.supabase.rpc(
                'match_locations',
                {
                    'query_embedding': embedding,
                    'match_threshold': threshold,
                    'match_count': 3  # Vérifier les 3 plus proches
                }
            ).execute()
            
            # Log si on trouve des matchs proches
            if response.data:
                for match in response.data:
                    logger.info(f"📊 Match trouvé: {match['name']} (similarité: {match['similarity']:.3f})")
            
            return len(response.data) > 0
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de la vérification de doublon: {str(e)}")
            return False
            
    def save_premium_poi_to_database(self, poi_data: Dict[str, Any], url: str, category: str, content: Dict[str, Any]) -> bool:
        """Sauvegarde un POI premium avec toutes les métadonnées enrichies"""
        try:
            # Structure enrichie pour la base de données
            location_data = {
                'name': poi_data['extracted']['name'] or poi_data['title'],
                'name_jp': poi_data['extracted'].get('name_jp'),
                'description': poi_data['description'],
                'summary': poi_data['extracted'].get('summary'),
                'category': category,
                'neighborhood': poi_data['extracted'].get('neighborhood'),
                'district': poi_data['extracted'].get('district'),
                'is_active': False,  # Brouillon par défaut
                'source_url': url,
                'source_name': self.site_name,
                'source_scraped_at': datetime.utcnow().isoformat(),
                'embedding': poi_data['embedding'],
                
                # Features enrichies
                'features': {
                    'keywords': poi_data['extracted'].get('keywords', []),
                    'price_range': poi_data['extracted'].get('price_range'),
                    'best_for': poi_data['extracted'].get('best_for', []),
                    'highlights': poi_data['extracted'].get('highlights', []),
                    'practical_info': poi_data['extracted'].get('practical_info', {}),
                    'original_categories': content['categories'],
                    'original_tags': content['tags'],
                    'images': content['images'][:3],  # Top 3 images
                    'quality_score': 0.95  # Score de qualité premium
                },
                
                # Métadonnées de génération
                'generation_metadata': {
                    'crawler_version': 'Premium V2',
                    'models_used': {
                        'classification': self.classification_model,
                        'generation': self.generation_model,
                        'embedding': self.embedding_model
                    },
                    'generation_date': datetime.utcnow().isoformat()
                }
            }
            
            # Si on a une adresse, l'ajouter
            if content.get('address'):
                location_data['address'] = content['address']
                
            # Insertion dans la table locations
            self.supabase.table('locations').insert(location_data).execute()
            
            logger.info(f"🌟 POI PREMIUM créé: {location_data['name']} ({category})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde du POI premium: {str(e)}")
            raise
            
    def mark_url_as_processed(self, url: str, status: str, error_details: str = None):
        """Marque une URL comme traitée avec détails optionnels"""
        try:
            data = {
                'url': url,
                'status': status,
                'processed_at': datetime.utcnow().isoformat()
            }
            
            if error_details:
                data['error_details'] = error_details
                
            self.supabase.table('processed_urls').insert(data).execute()
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du marquage de l'URL: {str(e)}")
            
    def process_single_url_premium(self, url: str) -> str:
        """Traite une URL unique avec pipeline de qualité premium"""
        try:
            logger.info(f"🔄 Traitement PREMIUM de: {url}")
            
            # Étape 1: Téléchargement du contenu enrichi
            html_content = self.download_page_content(url)
            rich_content = self.extract_rich_content(html_content, url)
            
            if len(rich_content['text']) < 200:
                logger.warning(f"⚠️ Contenu trop court pour {url}")
                return 'skipped_not_a_poi'
                
            # Étape 2: Classification premium avec catégorisation
            is_poi, category = self.classify_as_poi_premium(rich_content)
            
            if not is_poi:
                logger.info(f"ℹ️ {url} n'est pas un POI")
                return 'skipped_not_a_poi'
                
            logger.info(f"✅ POI détecté - Catégorie: {category}")
            
            # Étape 3: Génération de description premium
            lovely_description = self.generate_premium_description(rich_content, category)
            logger.info(f"✨ Description premium générée ({len(lovely_description)} caractères)")
            
            # Étape 4: Extraction de données structurées enrichies
            structured_data = self.extract_structured_data_premium(
                rich_content, 
                lovely_description, 
                category
            )
            
            # Étape 5: Génération d'embedding haute qualité
            embedding = self.get_premium_embedding(lovely_description)
            
            # Étape 6: Vérification stricte des doublons
            is_duplicate = self.check_semantic_duplicate(embedding)
            
            if is_duplicate:
                logger.info(f"ℹ️ Doublon détecté pour {url}")
                return 'skipped_duplicate'
                
            # Étape 7: Sauvegarde enrichie
            poi_data = {
                'title': rich_content['title'],
                'description': lovely_description,
                'extracted': structured_data,
                'embedding': embedding
            }
            
            self.save_premium_poi_to_database(poi_data, url, category, rich_content)
            
            return 'success'
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du traitement premium de {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return 'failed'
            
    def run(self):
        """Méthode principale d'exécution du crawler premium"""
        try:
            # Log de démarrage
            start_time = time.time()
            self.log_to_database(
                'STARTED',
                f'🌟 Lancement du scan PREMIUM pour {self.site_name} (Tous les sitemaps)',
                {'sitemaps_count': len(self.TOKYO_CHEAPO_SITEMAPS)}
            )
            
            # Récupération de TOUTES les URLs
            logger.info("🚀 Démarrage du crawler PREMIUM Yorimichi")
            all_urls = self.fetch_all_sitemap_urls()
            processed_urls = self.get_processed_urls()
            
            # Calcul des URLs à traiter
            urls_to_process = [url for url in all_urls if url not in processed_urls]
            
            if not urls_to_process:
                message = "Aucune nouvelle URL à traiter."
                logger.info(f"✅ {message}")
                self.log_to_database('SUCCESS', message)
                return
                
            logger.info(f"📋 {len(urls_to_process)} nouvelles URLs à traiter en mode PREMIUM")
            estimated_cost = len(urls_to_process) * 0.10  # ~0.10$ par URL en premium
            logger.info(f"💰 Coût estimé: ~${estimated_cost:.2f}")
            
            # Boucle de traitement principale
            for idx, url in enumerate(urls_to_process, 1):
                try:
                    # Traitement premium de l'URL
                    status = self.process_single_url_premium(url)
                    
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
                    
                    # Log de progression détaillé
                    if self.processed_count % self.batch_log_interval == 0:
                        elapsed_time = time.time() - start_time
                        rate = self.processed_count / (elapsed_time / 60)  # URLs par minute
                        remaining = len(urls_to_process) - self.processed_count
                        eta_minutes = remaining / rate if rate > 0 else 0
                        
                        progress_msg = (
                            f"🎯 Progression: {self.processed_count}/{len(urls_to_process)} URLs\n"
                            f"✅ {self.success_count} POIs PREMIUM créés\n"
                            f"⏭️ {self.skip_count} ignorés\n"
                            f"❌ {self.error_count} erreurs\n"
                            f"⏱️ Vitesse: {rate:.1f} URLs/min\n"
                            f"⏳ ETA: {eta_minutes:.0f} minutes\n"
                            f"💰 Coût actuel: ~${self.total_cost_estimate:.2f}"
                        )
                        logger.info(progress_msg)
                        self.log_to_database('RUNNING', progress_msg, {
                            'processed': self.processed_count,
                            'total': len(urls_to_process),
                            'success': self.success_count,
                            'skipped': self.skip_count,
                            'errors': self.error_count,
                            'cost_estimate': self.total_cost_estimate,
                            'rate_per_minute': rate
                        })
                        
                    # Délai entre les requêtes (plus long pour éviter rate limits)
                    time.sleep(self.delay_between_urls)
                    
                except Exception as e:
                    logger.error(f"❌ Erreur non gérée pour {url}: {str(e)}")
                    self.error_count += 1
                    self.mark_url_as_processed(url, 'failed', str(e))
                    self.log_to_database('ERROR', f"Erreur sur {url}", {'error': str(e)})
                    continue
                    
            # Statistiques finales
            total_time = time.time() - start_time
            final_message = (
                f"🌟 Scan PREMIUM terminé avec succès!\n"
                f"📊 Total traité: {self.processed_count}\n"
                f"✨ POIs PREMIUM créés: {self.success_count}\n"
                f"⏭️ Ignorés: {self.skip_count}\n"
                f"❌ Erreurs: {self.error_count}\n"
                f"⏱️ Durée totale: {total_time/60:.1f} minutes\n"
                f"💰 Coût total estimé: ${self.total_cost_estimate:.2f}"
            )
            
            logger.info(f"🎉 {final_message}")
            self.log_to_database('SUCCESS', final_message, {
                'total_processed': self.processed_count,
                'success': self.success_count,
                'skipped': self.skip_count,
                'errors': self.error_count,
                'duration_seconds': total_time,
                'total_cost': self.total_cost_estimate,
                'cost_per_poi': self.total_cost_estimate / self.success_count if self.success_count > 0 else 0
            })
            
        except Exception as e:
            error_msg = f"Erreur fatale du crawler premium: {str(e)}"
            logger.error(f"💥 {error_msg}")
            logger.error(traceback.format_exc())
            self.log_to_database('ERROR', error_msg, {'traceback': traceback.format_exc()})
            raise


def main():
    """Point d'entrée principal du script premium"""
    try:
        print("""
╔══════════════════════════════════════════════════════════════╗
║          YORIMICHI PREMIUM CRAWLER - QUALITY EDITION         ║
║                                                              ║
║  🌟 Modèles: GPT-4 Turbo pour tout                         ║
║  ✨ Descriptions: Uniques et captivantes                    ║
║  📊 Données: Extraction enrichie avec métadonnées           ║
║  🎯 Qualité: Maximum, sans compromis                        ║
║                                                              ║
║  💰 Coût estimé: ~0.10$ par POI                            ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        crawler = YorimichiPremiumCrawler()
        crawler.run()
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ Arrêt manuel du crawler premium")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Erreur fatale: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()