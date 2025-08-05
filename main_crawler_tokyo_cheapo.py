#!/usr/bin/env python3
"""
Worker Intelligent Yorimichi - TOKYO CHEAPO EDITION
Version spécialement optimisée pour extraire le maximum d'infos de Tokyo Cheapo
"""

import os
import sys
import time
import json
import logging
import re
from datetime import datetime, timezone
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
        logging.FileHandler('yorimichi_tokyo_cheapo.log')
    ]
)
logger = logging.getLogger('TokyoCheapoCrawler')


class TokyoCheapoCrawler:
    """Crawler optimisé spécifiquement pour Tokyo Cheapo"""
    
    # Mapping des catégories Tokyo Cheapo vers les catégories Yorimichi (en anglais)
    CATEGORY_MAPPING = {
        'TEMPLE': 'Temple',
        'SHRINE': 'Temple',  # Group with Temple
        'MUSEUM': 'Museum',
        'PARK': 'Park',
        'RESTAURANT': 'Restaurant',
        'CAFE': 'Café',  # Keep accent as in DB
        'BAR': 'Bar',
        'HOTEL': 'Accommodation',  # Use existing tag
        'MARKET': 'Market',  # Will create as feature
        'SHOP': 'Shopping',  # Use as feature, not category
        'ATTRACTION': 'Observatory',  # Closest existing category
        'ONSEN': 'Onsen',  # Will create if needed
        'AUTRE': 'Other'  # Will create if needed
    }
    
    # Mapping pour les types de visiteurs (enrichi pour agent touristique)
    VISITOR_TYPE_MAPPING = {
        'budget': 'Budget',  # Use as price_range
        'culture': 'Culture',  # Use as feature
        'food': 'Dining',  # Already exists as feature
        'family': 'Family Friendly',  # Already exists
        'luxury': 'Luxury',  # Will create as price_range
        'local': 'Local',  # Already exists as ambiance
        'tourist': 'Tourist',  # Already exists as ambiance
        'traditional': 'Traditional',  # Already exists as ambiance
        'modern': 'Modern',  # Already exists as ambiance
        'entertainment': 'Entertainment',  # Already exists as feature
        'nightlife': 'Nightlife',  # Already exists as feature
        'shopping': 'Shopping',  # Already exists as feature
        # New for tourism agent
        'romantic': 'Romantic',  # For couples
        'solo': 'Solo Traveler',  # Solo travelers
        'business': 'Business Traveler',  # Business trips
        'photography': 'Photography Spot',  # Photo opportunities
        'foodie': 'Foodie Paradise',  # Food enthusiasts
        'adventure': 'Adventure',  # Adventure seekers
        'relaxation': 'Relaxation',  # Peaceful spots
        'rainy_day': 'Rainy Day Activity',  # Indoor activities
        'instagram': 'Instagram Worthy',  # Social media spots
        'hidden_gem': 'Hidden Gem',  # Off the beaten path
        'must_see': 'Must See',  # Essential Tokyo
        'otaku': 'Otaku Culture',  # Anime/manga fans
        'wellness': 'Wellness',  # Health & wellness
    }
    
    # Configuration des sitemaps par ordre de valeur
    TOKYO_CHEAPO_SITEMAPS = {
        'attractions': [
            "https://tokyocheapo.com/place-sitemap1.xml",
            "https://tokyocheapo.com/place-sitemap2.xml", 
            "https://tokyocheapo.com/place-sitemap3.xml",
        ],
        'restaurants': [
            "https://tokyocheapo.com/restaurant-sitemap1.xml",
            "https://tokyocheapo.com/restaurant-sitemap2.xml",
        ],
        'accommodation': [
            "https://tokyocheapo.com/accommodation-sitemap.xml",
        ],
        'events': [
            "https://tokyocheapo.com/event-sitemap1.xml",
            "https://tokyocheapo.com/event-sitemap2.xml",
        ]
    }
    
    def __init__(self):
        """Initialisation avec configuration optimale pour Tokyo Cheapo"""
        # Charger les variables d'environnement
        if os.path.exists('.env.local'):
            load_dotenv('.env.local')
        else:
            load_dotenv()
        
        # Validation
        self.validate_environment()
        
        # Clients
        self.supabase = create_client(
            os.getenv('NEXT_PUBLIC_SUPABASE_URL'),
            os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        )
        
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        self.scrapingbee_api_key = os.getenv('SCRAPINGBEE_API_KEY')
        
        # Configuration
        self.site_name = "Tokyo Cheapo"
        self.agent_name = "Tokyo Cheapo Specialist Crawler"
        
        # Stats
        self.processed_count = 0
        self.success_count = 0
        self.skip_count = 0
        self.error_count = 0
        self.total_cost_estimate = 0.0
        
        # Load neighborhoods from database
        self.neighborhoods = self.load_neighborhoods()
        
        # Charger les URLs déjà scrapées au démarrage
        self.existing_urls = set()
        try:
            existing = self.supabase.table('locations') \
                .select('source_url') \
                .like('source_url', '%tokyocheapo.com%') \
                .execute()
            
            if existing.data:
                self.existing_urls = {loc['source_url'] for loc in existing.data if loc.get('source_url')}
                logger.info(f"✅ {len(self.existing_urls)} URLs Tokyo Cheapo déjà scrapées")
        except Exception as e:
            logger.warning(f"⚠️ Impossible de charger les URLs existantes: {e}")
        
    def validate_environment(self):
        """Valide les variables d'environnement"""
        required_vars = [
            'NEXT_PUBLIC_SUPABASE_URL',
            'SUPABASE_SERVICE_ROLE_KEY',
            'OPENAI_API_KEY',
            'SCRAPINGBEE_API_KEY'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            error_msg = f"Variables manquantes: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise EnvironmentError(error_msg)
            
        logger.info("✅ Configuration validée")
        
    def load_neighborhoods(self) -> Dict[str, str]:
        """Charge la liste des neighborhoods depuis Supabase"""
        try:
            result = self.supabase.table('neighborhoods').select('id, name').eq('is_active', True).execute()
            neighborhoods = {item['name']: item['id'] for item in result.data}
            logger.info(f"✅ {len(neighborhoods)} neighborhoods chargés")
            return neighborhoods
        except Exception as e:
            logger.error(f"Erreur chargement neighborhoods: {str(e)}")
            return {}
        
    def extract_tokyo_cheapo_data(self, html: str, url: str) -> Dict[str, Any]:
        """Extraction spécialisée pour Tokyo Cheapo"""
        logger.info(f"📄 Step 1/5: Extracting data from HTML")
        soup = BeautifulSoup(html, 'html.parser')
        
        data = {
            'title': '',
            'content': '',
            'address': None,
            'hours': None,
            'price': None,
            'nearest_stations': [],
            'tags': [],
            'meta_description': '',
            'images': [],
            'latitude': None,
            'longitude': None
        }
        
        # Titre
        h1 = soup.find('h1')
        if h1:
            data['title'] = h1.get_text(strip=True)
            
        # Meta description
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            data['meta_description'] = meta_desc.get('content', '')
            
        # Contenu principal (structure Tokyo Cheapo)
        content_div = soup.find('div', class_='entry-content') or soup.find('article')
        if content_div:
            # Garder la structure pour mieux comprendre
            data['content'] = content_div.get_text(separator='\n', strip=True)
            
            # Extraire les infos pratiques du contenu
            content_text = content_div.get_text()
            
            # Adresse (patterns Tokyo Cheapo)
            address_patterns = [
                r'Address:?\s*([^\n]+)',
                r'Location:?\s*([^\n]+)',
                r'\d+-\d+-\d+\s+\w+,\s*\w+\s*Ward',
            ]
            for pattern in address_patterns:
                match = re.search(pattern, content_text, re.IGNORECASE)
                if match:
                    data['address'] = match.group(1).strip()
                    break
                    
            # Horaires
            hours_patterns = [
                r'Hours?:?\s*([^\n]+)',
                r'Open:?\s*([^\n]+)',
                r'Opening hours?:?\s*([^\n]+)',
                r'(\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2})'
            ]
            for pattern in hours_patterns:
                match = re.search(pattern, content_text, re.IGNORECASE)
                if match:
                    data['hours'] = match.group(1).strip()
                    break
                    
            # Prix
            price_patterns = [
                r'Price:?\s*([^\n]+)',
                r'Cost:?\s*([^\n]+)',
                r'¥[\d,]+',
                r'(\d+\s*yen)'
            ]
            price_mentions = []
            for pattern in price_patterns:
                matches = re.findall(pattern, content_text, re.IGNORECASE)
                price_mentions.extend(matches)
            if price_mentions:
                data['price'] = ' | '.join(price_mentions[:3])  # Top 3 prix trouvés
                
            # Stations (très important pour Tokyo)
            station_patterns = [
                r'(?:Station|駅)[:\s]+([^\n,]+)',
                r'Nearest station:?\s*([^\n]+)',
                r'Access:?\s*([^\n]+)',
                r'(\w+\s+Station)'
            ]
            stations = []
            for pattern in station_patterns:
                matches = re.findall(pattern, content_text, re.IGNORECASE)
                stations.extend(matches)
            # Nettoyer et dédupliquer
            data['nearest_stations'] = list(set([s.strip() for s in stations if 'Station' in s]))[:3]
            
        # Tags (structure Tokyo Cheapo)
        tag_links = soup.find_all('a', {'rel': 'tag'})
        data['tags'] = [tag.get_text(strip=True) for tag in tag_links]
        
        # Images principales (de Tokyo Cheapo - souvent de mauvaise qualité)
        images = soup.find_all('img', limit=5)
        data['images'] = [img.get('src', '') for img in images if img.get('src') and 'logo' not in img.get('src', '').lower()]
        
        # Coordonnées GPS (si disponibles)
        # Chercher dans la carte Google Maps iframe ou scripts
        map_iframe = soup.find('iframe', {'src': lambda x: x and 'maps' in x})
        if map_iframe:
            src = map_iframe.get('src', '')
            # Extraire lat/lng de l'URL Google Maps
            lat_match = re.search(r'!3d([-\d.]+)', src)
            lng_match = re.search(r'!4d([-\d.]+)', src)
            if lat_match and lng_match:
                data['latitude'] = float(lat_match.group(1))
                data['longitude'] = float(lng_match.group(1))
        
        # Alternative: chercher dans les scripts JS
        if not data['latitude']:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # Pattern pour Tokyo Cheapo maps
                    coords_match = re.search(r'lat["\']?\s*:\s*([-\d.]+).*?lng["\']?\s*:\s*([-\d.]+)', script.string, re.DOTALL)
                    if coords_match:
                        data['latitude'] = float(coords_match.group(1))
                        data['longitude'] = float(coords_match.group(2))
                        break
        
        return data
        
    def classify_and_enrich(self, extracted_data: Dict[str, Any], url: str) -> Tuple[bool, str, Dict]:
        """Classification et enrichissement intelligent"""
        logger.info(f"🤖 Step 2/5: Classifying POI with GPT-3.5")
        try:
            # Prompt optimized for Tokyo Cheapo (in English)
            neighborhoods_list = ', '.join(self.neighborhoods.keys())
            prompt = f"""You are a Tokyo expert who knows Tokyo Cheapo website perfectly.
            
Analyze this information and determine:
1. Is this a UNIQUE physical place that can be visited (not a general article or guide)?
2. If YES, categorize precisely.
3. Identify the exact neighborhood from this list: {neighborhoods_list}

Reply in JSON: {{
  "is_poi": true/false,
  "category": "TEMPLE|SHRINE|MUSEUM|PARK|RESTAURANT|CAFE|BAR|HOTEL|MARKET|SHOP|ATTRACTION|ONSEN|OTHER",
  "subcategory": "more specific if possible",
  "neighborhood": "exact name from the list above, or null if not found",
  "type_visitor": ["budget", "culture", "food", "family", "romantic", "solo", "photography", "rainy_day", "must_see", etc.],
  "best_time": "morning|afternoon|evening|night|anytime",
  "time_needed": "30min|1h|2h|3h|half-day|full-day",
  "reservation": "required|recommended|not-needed|unknown",
  "english_friendly": true/false
}}"""

            context = f"""
Titre: {extracted_data['title']}
URL: {url}
Description: {extracted_data['meta_description']}
Tags: {', '.join(extracted_data['tags'])}
Adresse: {extracted_data['address']}
Stations: {', '.join(extracted_data['nearest_stations'])}
Contenu (extrait): {extracted_data['content'][:1500]}
"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context}
                ],
                temperature=0.2,
                max_tokens=150,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            self.total_cost_estimate += 0.003
            logger.debug(f"📊 Classification result: {result}")
            
            # Enrichir avec les données extraites
            if result.get('is_poi', False):
                logger.info(f"✅ Confirmed as POI: {result.get('category')} in {result.get('neighborhood', 'Unknown')}")
                enriched = {
                    'is_poi': True,
                    'category': result.get('category', 'AUTRE'),
                    'subcategory': result.get('subcategory'),
                    'neighborhood': result.get('neighborhood') or self.extract_neighborhood_from_address(extracted_data['address']),
                    'visitor_types': result.get('type_visitor', []),
                    'practical_info': {
                        'address': extracted_data['address'],
                        'hours': extracted_data['hours'],
                        'price': extracted_data['price'],
                        'nearest_stations': extracted_data['nearest_stations']
                    }
                }
                return True, result.get('category', 'AUTRE'), enriched
            else:
                return False, 'NOT_POI', {}
                
        except Exception as e:
            logger.error(f"Erreur classification: {str(e)}")
            return False, 'ERROR', {}
            
    def get_wikimedia_image(self, place_name: str, category: str) -> Optional[str]:
        """Récupère une image gratuite depuis Wikimedia Commons (100% légal)"""
        try:
            # API Wikimedia Commons
            search_url = "https://commons.wikimedia.org/w/api.php"
            
            # 1. Rechercher l'image
            search_params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': f'{place_name} Tokyo',
                'srnamespace': 6,  # File namespace
                'srlimit': 3  # Top 3 résultats
            }
            
            response = requests.get(search_url, params=search_params, timeout=5)
            data = response.json()
            
            if not data.get('query', {}).get('search'):
                # Essayer avec des termes plus génériques
                search_params['srsearch'] = f'{category} Tokyo Japan'
                response = requests.get(search_url, params=search_params, timeout=5)
                data = response.json()
            
            if data.get('query', {}).get('search'):
                # 2. Obtenir l'URL de l'image
                for result in data['query']['search']:
                    file_title = result['title']
                    
                    image_params = {
                        'action': 'query',
                        'format': 'json',
                        'titles': file_title,
                        'prop': 'imageinfo',
                        'iiprop': 'url|mime',
                        'iiurlwidth': 800  # Largeur optimale pour web
                    }
                    
                    img_response = requests.get(search_url, params=image_params, timeout=5)
                    img_data = img_response.json()
                    
                    pages = img_data.get('query', {}).get('pages', {})
                    for page in pages.values():
                        if 'imageinfo' in page:
                            imageinfo = page['imageinfo'][0]
                            # Vérifier que c'est une image (pas un PDF ou autre)
                            if imageinfo.get('mime', '').startswith('image/'):
                                image_url = imageinfo.get('thumburl') or imageinfo.get('url')
                                logger.debug(f"✓ Image Wikimedia trouvée: {file_title}")
                                return image_url
                                
        except Exception as e:
            logger.warning(f"Erreur Wikimedia: {str(e)}")
            
        return None
    
    def geocode_address(self, address: str) -> Dict[str, Optional[float]]:
        """Geocode une adresse pour obtenir lat/lng (comme le backoffice)"""
        if not address or address == 'Tokyo':
            logger.debug("⏭️ Geocoding skipped: empty or generic address")
            return {'lat': None, 'lng': None}
            
        try:
            logger.info(f"🌍 Geocoding address: {address}")
            # Utiliser Nominatim (OpenStreetMap) - Gratuit, pas de clé API
            # Respecter les limites : 1 requête/seconde
            time.sleep(1)  # Rate limiting
            
            geocode_url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': f"{address}, Tokyo, Japan",
                'format': 'json',
                'limit': 1,
                'accept-language': 'en'
            }
            headers = {
                'User-Agent': 'Yorimichi Tourism Crawler/1.0'  # Required by Nominatim
            }
            
            logger.debug(f"📡 Calling Nominatim API with query: {params['q']}")
            response = requests.get(geocode_url, params=params, headers=headers, timeout=10)
            data = response.json()
            
            if data and len(data) > 0:
                result = data[0]
                lat = float(result['lat'])
                lng = float(result['lon'])
                logger.info(f"✅ Geocoding successful: {address} → {lat}, {lng}")
                logger.debug(f"📍 Full result: {result.get('display_name', 'N/A')}")
                return {'lat': lat, 'lng': lng}
            else:
                logger.warning(f"⚠️ No geocoding results for: {address}")
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ Geocoding timeout for address: {address}")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Geocoding network error: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Geocoding unexpected error: {str(e)}")
            
        return {'lat': None, 'lng': None}
    
    def extract_neighborhood_from_address(self, address: str) -> Optional[str]:
        """Extrait le quartier depuis l'adresse"""
        if not address:
            return None
            
        # Quartiers connus de Tokyo
        neighborhoods = [
            'Shibuya', 'Shinjuku', 'Harajuku', 'Asakusa', 'Ginza', 
            'Roppongi', 'Akihabara', 'Ueno', 'Ikebukuro', 'Odaiba',
            'Nakano', 'Kichijoji', 'Shimokitazawa', 'Daikanyama', 'Ebisu',
            'Meguro', 'Shinagawa', 'Chiyoda', 'Minato', 'Taito'
        ]
        
        address_lower = address.lower()
        for hood in neighborhoods:
            if hood.lower() in address_lower:
                return hood
                
        # Chercher le pattern "XXX-ku" ou "XXX Ward"
        ward_match = re.search(r'(\w+)[-\s](?:ku|ward)', address, re.IGNORECASE)
        if ward_match:
            return ward_match.group(1)
            
        return None
        
    def generate_unique_description(self, data: Dict[str, Any], category: str, enriched: Dict) -> str:
        """Génère une description unique et captivante avec GPT-4"""
        logger.info(f"✍️ Step 3/5: Generating unique description with GPT-4")
        try:
            # Adapt style to place type (in English)
            style_map = {
                'RESTAURANT': "appetizing and flavorful, evoking tastes and aromas",
                'TEMPLE': "spiritual and serene, capturing the sacred atmosphere",
                'SHRINE': "mystical and traditional, evoking historical significance",
                'MUSEUM': "cultural and enriching, highlighting educational value",
                'PARK': "natural and peaceful, describing scenic beauty",
                'MARKET': "vibrant and bustling, capturing local energy",
                'ONSEN': "relaxing and authentic, evoking wellness and tradition",
                'ATTRACTION': "exciting and memorable, inspiring curiosity"
            }
            
            style = style_map.get(category, "engaging and informative")
            
            # Context for GPT-4 (in English)
            prompt = f"""You are an expert travel guide writer specializing in Tokyo, known for your vivid descriptions.
            
Create a {style} description of this place in 150-200 words.
IMPORTANT: 
- The description must be 100% ORIGINAL in ENGLISH
- Evoke SENSATIONS and EMOTIONS visitors will experience
- Include PRACTICAL details subtly woven into the narrative
- Adapt the tone for budget-conscious travelers (Tokyo Cheapo style)
- DO NOT COPY any phrases from the source text
- Write in engaging, natural English

Also subtly include:
- Best time to visit (if relevant)
- How long to spend there
- Any insider tips or local secrets
- What makes it special or unique
- Who would enjoy it most (couples, families, solo travelers, etc.)"""

            context = f"""
Lieu: {data['title']}
Type: {category} {enriched.get('subcategory', '')}
Quartier: {enriched.get('neighborhood', 'Tokyo')}
Pour: {', '.join(enriched.get('visitor_types', ['tous']))}

Infos pratiques:
- Stations proches: {', '.join(data['nearest_stations'])}
- Prix: {data['price'] or 'Gratuit/Variable'}
- Horaires: {data['hours'] or 'Variable'}

Contexte du site:
{data['content'][:2000]}
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context}
                ],
                temperature=0.85,
                max_tokens=400,
                presence_penalty=0.6
            )
            
            description = response.choices[0].message.content.strip()
            self.total_cost_estimate += 0.04
            logger.info(f"✅ Description generated: {len(description)} characters")
            logger.debug(f"📝 Preview: {description[:100]}...")
            
            return description
            
        except Exception as e:
            logger.error(f"Erreur génération: {str(e)}")
            raise
            
    def get_or_create_tag(self, tag_name: str, tag_type: str) -> Optional[str]:
        """Récupère ou crée un tag et retourne son ID"""
        try:
            # Chercher si le tag existe déjà
            result = self.supabase.table('tags').select('id').eq('name', tag_name).eq('tag_type', tag_type).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['id']
            
            # Créer le tag s'il n'existe pas
            slug = tag_name.lower().replace(' ', '-').replace('/', '-').replace('&', 'and')
            new_tag = self.supabase.table('tags').insert({
                'name': tag_name,
                'tag_type': tag_type,
                'slug': slug
            }).execute()
            
            if new_tag.data and len(new_tag.data) > 0:
                logger.debug(f"✓ Tag créé: {tag_name} ({tag_type})")
                return new_tag.data[0]['id']
                
        except Exception as e:
            logger.warning(f"⚠️ Impossible de gérer le tag '{tag_name}' ({tag_type}): {str(e)}")
            # On continue sans ce tag - on pourra le corriger plus tard
        return None
    
    def save_enhanced_poi(self, data: Dict, description: str, category: str, enriched: Dict, url: str):
        """Sauvegarde le POI avec toutes les infos Tokyo Cheapo"""
        logger.info(f"💾 Step 4/5: Saving POI to database")
        try:
            logger.debug("🔤 Generating embedding...")
            # Générer l'embedding
            embedding_response = self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=description[:8000]
            )
            embedding = embedding_response.data[0].embedding
            self.total_cost_estimate += 0.0004
            
            # Vérifier les doublons
            logger.debug("🔍 Checking for duplicates...")
            dup_check = self.supabase.rpc('match_locations', {
                'query_embedding': embedding,
                'match_threshold': 0.92,
                'match_count': 1
            }).execute()
            
            if len(dup_check.data) > 0:
                logger.warning(f"⚠️ Duplicate detected: {data['title']} (similarity: {dup_check.data[0].get('similarity', 'N/A')})")
                return 'skipped_duplicate'
                
            # Get or create neighborhood_id from enriched data
            neighborhood_id = None
            if enriched.get('neighborhood'):
                if enriched['neighborhood'] in self.neighborhoods:
                    neighborhood_id = self.neighborhoods[enriched['neighborhood']]
                    logger.debug(f"✓ Neighborhood trouvé: {enriched['neighborhood']}")
                else:
                    # Create new neighborhood if it doesn't exist
                    try:
                        new_neighborhood = self.supabase.table('neighborhoods').insert({
                            'name': enriched['neighborhood'],
                            'is_active': True
                        }).execute()
                        
                        if new_neighborhood.data and len(new_neighborhood.data) > 0:
                            neighborhood_id = new_neighborhood.data[0]['id']
                            # Add to local cache
                            self.neighborhoods[enriched['neighborhood']] = neighborhood_id
                            logger.info(f"✓ Nouveau neighborhood créé: {enriched['neighborhood']}")
                    except Exception as e:
                        logger.warning(f"⚠️ Impossible de créer le neighborhood '{enriched['neighborhood']}': {str(e)}")
            
            # Préparer les données pour Supabase
            logger.debug(f"📦 Preparing data for insertion...")
            location_data = {
                'name': data['title'],
                'name_jp': None,  # À extraire si présent dans le contenu
                'description': description,
                'summary': description[:100] + "..." if len(description) > 100 else description,
                'neighborhood_id': neighborhood_id,  # Use the proper foreign key
                'address': data['address'],
                'latitude': data.get('latitude') or self.geocode_address(data['address']).get('lat'),
                'longitude': data.get('longitude') or self.geocode_address(data['address']).get('lng'),
                'is_active': False,
                'source_url': url,
                'source_name': self.site_name,
                'source_scraped_at': datetime.now(timezone.utc).isoformat(),
                'embedding': embedding,
                'image_url': None,  # Pas d'image pour le moment
                
                # Features enrichies spéciales Tokyo Cheapo
                'features': {
                    'visitor_types': enriched.get('visitor_types', []),
                    'original_tags': data['tags'],
                    'price_info': data['price'],
                    'opening_hours': data['hours'],
                    'nearest_stations': data['nearest_stations'],
                    'images': data['images'][:3],
                    'tokyo_cheapo_data': True,
                    'practical_info': enriched.get('practical_info', {}),
                    # New tourism agent features
                    'best_time': enriched.get('best_time', 'anytime'),
                    'time_needed': enriched.get('time_needed', '1h'),
                    'reservation': enriched.get('reservation', 'unknown'),
                    'english_friendly': enriched.get('english_friendly', True),
                    'coordinates': {
                        'lat': data.get('latitude'),
                        'lng': data.get('longitude')
                    } if data.get('latitude') else None
                },
                
                'metadata': {
                    'crawler_version': 'Tokyo Cheapo Specialist v1',
                    'extraction_date': datetime.now(timezone.utc).isoformat()
                }
            }
            
            # Insérer dans la base
            logger.debug("📤 Inserting location into database...")
            location_result = self.supabase.table('locations').insert(location_data).execute()
            
            if not location_result.data or len(location_result.data) == 0:
                logger.error("Erreur: Impossible de créer la location")
                return 'failed'
                
            location_id = location_result.data[0]['id']
            
            # Créer les associations de tags
            logger.info(f"🏷️ Step 5/5: Creating tag associations")
            tags_to_create = []
            
            # 1. Tag de catégorie principale (avec mapping)
            mapped_category = self.CATEGORY_MAPPING.get(category, category)
            
            # Handle special cases where some categories should be features
            if category in ['MARKET', 'SHOP']:
                # These are features, not categories
                feature_tag_id = self.get_or_create_tag(mapped_category, 'feature')
                if feature_tag_id:
                    tags_to_create.append({
                        'location_id': location_id,
                        'tag_id': feature_tag_id
                    })
                # Also add a default category
                default_category_id = self.get_or_create_tag('Shopping', 'feature')
                if default_category_id:
                    tags_to_create.append({
                        'location_id': location_id,
                        'tag_id': default_category_id
                    })
            else:
                # Normal category tag
                category_tag_id = self.get_or_create_tag(mapped_category, 'category')
                if category_tag_id:
                    tags_to_create.append({
                        'location_id': location_id,
                        'tag_id': category_tag_id
                    })
            
            # 2. Tags de quartier - Removed since we use neighborhood_id foreign key now
            
            # 3. Tags de type de visiteur (avec mapping et types corrects)
            for visitor_type in enriched.get('visitor_types', []):
                # Map visitor type and determine correct tag type
                mapped_visitor = self.VISITOR_TYPE_MAPPING.get(visitor_type.lower(), visitor_type)
                
                # Determine tag type based on mapping
                if visitor_type.lower() in ['budget', 'luxury']:
                    tag_type = 'price_range'
                elif visitor_type.lower() in ['local', 'tourist', 'traditional', 'modern']:
                    tag_type = 'ambiance'
                else:
                    tag_type = 'feature'
                
                visitor_tag_id = self.get_or_create_tag(mapped_visitor, tag_type)
                if visitor_tag_id:
                    tags_to_create.append({
                        'location_id': location_id,
                        'tag_id': visitor_tag_id
                    })
            
            # 4. Tag de prix si gratuit
            if data.get('price') and 'free' in data['price'].lower():
                free_tag_id = self.get_or_create_tag('Free', 'feature')  # Free already exists as feature
                if free_tag_id:
                    tags_to_create.append({
                        'location_id': location_id,
                        'tag_id': free_tag_id
                    })
            
            # Insérer tous les tags en une fois (avec gestion d'erreur souple)
            if tags_to_create:
                try:
                    logger.debug(f"📤 Inserting {len(tags_to_create)} tag associations...")
                    self.supabase.table('location_tags').insert(tags_to_create).execute()
                    logger.info(f"✅ {len(tags_to_create)} tags successfully associated")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur lors de l'association des tags: {str(e)}")
                    # On continue quand même - on pourra retraiter plus tard
            
            logger.info(f"🎉 POI successfully created: {data['title']}")
            logger.info(f"   📍 Category: {category}")
            logger.info(f"   🏘️ Neighborhood: {enriched.get('neighborhood', 'Tokyo')}")
            logger.info(f"   🏷️ Tags: {len(tags_to_create)}")
            logger.info(f"   📏 Coordinates: {location_data.get('latitude', 'N/A')}, {location_data.get('longitude', 'N/A')}")
            
            # Ajouter à la liste des URLs scrapées
            if 'source_url' in location_data:
                self.existing_urls.add(location_data['source_url'])
            
            return 'success'
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {str(e)}")
            return 'failed'
            
    def process_url(self, url: str) -> str:
        """Traite une URL complète"""
        try:
            # Vérifier si c'est une image
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']
            if any(url.lower().endswith(ext) for ext in image_extensions):
                logger.info(f"🖼️ Image ignorée: {url}")
                self.skip_count += 1
                return 'skipped_not_a_poi'  # Utiliser un statut existant
            
            # Vérifier si l'URL est déjà scrapée
            if url in self.existing_urls:
                logger.info(f"⏭️ URL déjà scrapée: {url}")
                self.skip_count += 1
                return 'skipped_existing'  # Utiliser un statut valide
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 Processing URL: {url}")
            logger.info(f"{'='*60}")
            
            # 1. Télécharger la page
            response = requests.get('https://app.scrapingbee.com/api/v1/', params={
                'api_key': self.scrapingbee_api_key,
                'url': url,
                'render_js': 'false',  # Pas besoin de JS pour Tokyo Cheapo
                'premium_proxy': 'false'  # Pas besoin de proxy premium
            }, timeout=60)
            response.raise_for_status()
            
            # 2. Extraire les données Tokyo Cheapo
            extracted = self.extract_tokyo_cheapo_data(response.text, url)
            
            if len(extracted['content']) < 200:
                logger.warning(f"⚠️ Contenu trop court")
                return 'skipped_not_a_poi'
                
            # 3. Classifier et enrichir
            is_poi, category, enriched = self.classify_and_enrich(extracted, url)
            
            if not is_poi:
                logger.info(f"ℹ️ Pas un POI: {extracted['title']}")
                return 'skipped_not_a_poi'
                
            # 4. Générer la description unique
            description = self.generate_unique_description(extracted, category, enriched)
            
            # 5. Sauvegarder
            return self.save_enhanced_poi(extracted, description, category, enriched, url)
            
        except Exception as e:
            logger.error(f"❌ Erreur: {str(e)}")
            logger.error(traceback.format_exc())
            return 'failed'
            
    def mark_url_processed(self, url: str, status: str):
        """Marque l'URL comme traitée"""
        try:
            self.supabase.table('processed_urls').insert({
                'url': url,
                'status': status
            }).execute()
        except Exception as e:
            logger.error(f"Erreur marquage URL: {str(e)}")
            
    def run(self, target='attractions', limit=None):
        """
        Lance le crawl
        target: 'attractions', 'restaurants', 'accommodation', 'all'
        limit: Nombre max d'URLs à traiter (pour tests)
        """
        try:
            logger.info(f"""
╔══════════════════════════════════════════════════════════════╗
║          TOKYO CHEAPO SPECIALIST CRAWLER                     ║
║                                                              ║
║  🎯 Extraction optimisée pour Tokyo Cheapo                  ║
║  📍 Adresses, stations, horaires, prix                      ║
║  ✨ Descriptions uniques avec GPT-4                         ║
║  🏷️ Catégorisation intelligente                            ║
╚══════════════════════════════════════════════════════════════╝
            """)
            
            # Déterminer les sitemaps à crawler
            if target == 'all':
                sitemaps = []
                for category_sitemaps in self.TOKYO_CHEAPO_SITEMAPS.values():
                    sitemaps.extend(category_sitemaps)
            else:
                sitemaps = self.TOKYO_CHEAPO_SITEMAPS.get(target, [])
                
            # Collecter toutes les URLs
            all_urls = []
            for sitemap_url in sitemaps:
                try:
                    resp = requests.get(sitemap_url, timeout=30)
                    soup = BeautifulSoup(resp.content, 'xml')
                    urls = [loc.text for loc in soup.find_all('loc')]
                    
                    # Filtrer les URLs WordPress inutiles
                    filtered_urls = []
                    for url in urls:
                        # Ignorer les uploads WordPress et autres fichiers
                        if any(pattern in url for pattern in [
                            '/wp-content/uploads/',
                            '/cdn.cheapoguides.com/wp-content/',
                            '.jpg', '.jpeg', '.png', '.gif', '.webp',
                            '/feed/', '/comments/', '/trackback/'
                        ]):
                            continue
                        # Garder seulement les vraies pages POI
                        if '/place/' in url:
                            filtered_urls.append(url)
                    
                    all_urls.extend(filtered_urls)
                    logger.info(f"✅ {len(filtered_urls)} URLs POI (sur {len(urls)} total) de {sitemap_url}")
                except Exception as e:
                    logger.error(f"Erreur sitemap {sitemap_url}: {e}")
                    
            # Récupérer les URLs déjà traitées
            processed = set()
            try:
                result = self.supabase.table('processed_urls').select('url').execute()
                processed = {row['url'] for row in result.data}
            except:
                pass
                
            # URLs à traiter
            to_process = [url for url in all_urls if url not in processed]
            
            if limit:
                to_process = to_process[:limit]
                
            logger.info(f"📊 {len(to_process)} URLs à traiter (sur {len(all_urls)} total)")
            
            # Estimation
            estimated_pois = int(len(to_process) * 0.4)
            estimated_cost = len(to_process) * 0.05
            estimated_time = len(to_process) * 15 / 60
            
            logger.info(f"""
📈 ESTIMATION:
- POIs attendus: ~{estimated_pois}
- Coût estimé: ~${estimated_cost:.2f}
- Temps estimé: ~{estimated_time:.0f} minutes
            """)
            
            if len(to_process) > 50 and not limit:
                confirm = input("Continuer ? (oui/non): ")
                if confirm.lower() != 'oui':
                    return
                    
            # Traitement
            start_time = time.time()
            
            for idx, url in enumerate(to_process, 1):
                try:
                    status = self.process_url(url)
                    
                    self.processed_count += 1
                    if status == 'success':
                        self.success_count += 1
                    elif status.startswith('skipped'):
                        self.skip_count += 1
                    else:
                        self.error_count += 1
                        
                    # Ne pas marquer les URLs déjà existantes
                    if status != 'skipped_existing':
                        self.mark_url_processed(url, status)
                    
                    # Progress
                    if idx % 5 == 0:  # More frequent updates
                        elapsed = time.time() - start_time
                        rate = self.processed_count / (elapsed / 60) if elapsed > 0 else 0
                        remaining = len(to_process) - idx
                        eta_minutes = remaining / rate if rate > 0 else 0
                        logger.info(f"""
📡 PROGRESS UPDATE:
⏱️  Progress: {idx}/{len(to_process)} ({idx/len(to_process)*100:.1f}%)
✅  POIs created: {self.success_count}
⏭️  Skipped: {self.skip_count}
❌  Errors: {self.error_count}
💰  Cost so far: ${self.total_cost_estimate:.2f}
📈  Speed: {rate:.1f} URLs/min
⏰  ETA: {eta_minutes:.1f} minutes
                        """)
                        
                    time.sleep(1.5)  # Respect rate limits
                    
                except Exception as e:
                    logger.error(f"Erreur URL {url}: {e}")
                    self.error_count += 1
                    self.mark_url_processed(url, 'failed')
                    
            # Résumé final
            duration = (time.time() - start_time) / 60
            logger.info(f"""
🎉 CRAWL TERMINÉ !
📊 Total traité: {self.processed_count}
✅ POIs créés: {self.success_count}
⏭️ Ignorés: {self.skip_count}
❌ Erreurs: {self.error_count}
⏱️ Durée: {duration:.1f} minutes
💰 Coût total: ${self.total_cost_estimate:.2f}
💎 Coût/POI: ${self.total_cost_estimate/self.success_count:.2f} par POI" if self.success_count > 0 else "N/A"
            """)
            
        except Exception as e:
            logger.error(f"Erreur fatale: {str(e)}")
            raise


def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=['attractions', 'restaurants', 'accommodation', 'all'], 
                       default='attractions', help='Type de contenu à crawler')
    parser.add_argument('--limit', type=int, help='Limite du nombre d\'URLs (pour tests)')
    
    args = parser.parse_args()
    
    crawler = TokyoCheapoCrawler()
    crawler.run(target=args.target, limit=args.limit)


if __name__ == "__main__":
    main()