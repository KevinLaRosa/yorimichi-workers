#!/usr/bin/env python3
"""
Test de la clé API Foursquare
"""

import os
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

print("🔍 Test de l'API Foursquare")
print("=" * 60)

api_key = os.getenv('FOURSQUARE_API_KEY')

if not api_key:
    print("❌ FOURSQUARE_API_KEY non trouvée dans .env.local")
    exit(1)

print(f"🔑 Clé API: {api_key[:10]}...{api_key[-4:]}")
print(f"📏 Longueur: {len(api_key)} caractères")

# Test 1: Recherche simple
print("\n📍 Test 1: Recherche de lieux à Tokyo...")
url = "https://api.foursquare.com/v3/places/search"
headers = {
    'Authorization': api_key,
    'Accept': 'application/json'
}
params = {
    'near': 'Tokyo, Japan',
    'query': 'Shibuya',
    'limit': 1
}

response = requests.get(url, headers=headers, params=params)
print(f"   Status: {response.status_code}")

if response.status_code == 200:
    print("   ✅ API fonctionne!")
    data = response.json()
    if data.get('results'):
        place = data['results'][0]
        print(f"   📍 Trouvé: {place.get('name')}")
elif response.status_code == 401:
    print("   ❌ Erreur 401: Clé API invalide ou mal formatée")
    print("   💡 Vérifiez que la clé commence par 'fsq' suivi de caractères alphanumériques")
    print("   💡 Format attendu: fsqXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    print(f"   Response: {response.text}")
elif response.status_code == 403:
    print("   ❌ Erreur 403: Quota dépassé ou accès refusé")
else:
    print(f"   ❌ Erreur {response.status_code}: {response.text}")

# Test 2: Vérifier le format de la clé
print("\n🔍 Test 2: Analyse du format de la clé...")
if api_key.startswith('fsq'):
    print("   ✅ La clé commence bien par 'fsq'")
else:
    print("   ❌ La clé devrait commencer par 'fsq'")
    
if len(api_key) > 30:
    print("   ✅ La longueur semble correcte")
else:
    print("   ❌ La clé semble trop courte")

print("\n" + "=" * 60)
print("\n💡 Si la clé ne fonctionne pas:")
print("   1. Allez sur https://foursquare.com/developers/apps")
print("   2. Créez un nouveau projet ou utilisez un existant")
print("   3. Copiez la clé API (format: fsqXXXXXXXXXXXXXXXXXXXX)")
print("   4. Mettez à jour .env.local avec FOURSQUARE_API_KEY=fsq...")
print("   5. NE PAS mettre de guillemets autour de la clé!")