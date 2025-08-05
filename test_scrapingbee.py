#!/usr/bin/env python3
"""
Test rapide de la clé ScrapingBee
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

api_key = os.getenv('SCRAPINGBEE_API_KEY')
print(f"🔑 Clé API: {api_key[:10]}...{api_key[-10:]}")

print("\n🧪 Test de la clé ScrapingBee...")

try:
    # Test simple sans render_js pour économiser les crédits
    response = requests.get('https://app.scrapingbee.com/api/v1/', params={
        'api_key': api_key,
        'url': 'https://httpbin.org/get'
    }, timeout=10)
    
    print(f"📡 Status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ La clé ScrapingBee fonctionne !")
        # Vérifier les crédits restants
        if 'Spb-Cost' in response.headers:
            print(f"💰 Coût de cette requête: {response.headers['Spb-Cost']} crédits")
    else:
        print(f"❌ Erreur: {response.status_code} - {response.text}")
        
except Exception as e:
    print(f"❌ Erreur: {e}")