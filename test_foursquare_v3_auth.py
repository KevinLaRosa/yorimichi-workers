#!/usr/bin/env python3
"""
Test des différentes méthodes d'authentification Foursquare API v3
"""

import os
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

print("🔍 Test d'authentification API Foursquare v3")
print("=" * 60)

api_key = os.getenv('FOURSQUARE_API_KEY')

if not api_key:
    print("❌ FOURSQUARE_API_KEY non trouvée")
    exit(1)

print(f"🔑 Clé API: {api_key[:10]}...{api_key[-4:]}")
print(f"📏 Format: {'Service API Key' if api_key.startswith('L5GK') else 'Legacy' if api_key.startswith('fsq') else 'Unknown'}")
print()

# URL de base pour les tests
url = "https://api.foursquare.com/v3/places/search"
base_params = {
    'near': 'Tokyo, Japan',
    'query': 'Shibuya',
    'limit': 1
}

# Test 1: Authorization header (sans préfixe)
print("📍 Test 1: Authorization header direct...")
headers = {
    'Authorization': api_key,
    'Accept': 'application/json'
}
response = requests.get(url, headers=headers, params=base_params)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print("   ✅ Méthode qui fonctionne!")
else:
    print(f"   ❌ Erreur: {response.json().get('message', response.text[:100])}")

# Test 2: Bearer token
print("\n📍 Test 2: Bearer token...")
headers = {
    'Authorization': f'Bearer {api_key}',
    'Accept': 'application/json'
}
response = requests.get(url, headers=headers, params=base_params)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print("   ✅ Méthode qui fonctionne!")
else:
    print(f"   ❌ Erreur: {response.json().get('message', response.text[:100])}")

# Test 3: X-API-Key header
print("\n📍 Test 3: X-API-Key header...")
headers = {
    'X-API-Key': api_key,
    'Accept': 'application/json'
}
response = requests.get(url, headers=headers, params=base_params)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print("   ✅ Méthode qui fonctionne!")
else:
    print(f"   ❌ Erreur: {response.json().get('message', response.text[:100])}")

# Test 4: Paramètre URL oauth_token
print("\n📍 Test 4: Paramètre URL oauth_token...")
params = base_params.copy()
params['oauth_token'] = api_key
headers = {'Accept': 'application/json'}
response = requests.get(url, headers=headers, params=params)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print("   ✅ Méthode qui fonctionne!")
else:
    print(f"   ❌ Erreur: {response.json().get('message', response.text[:100])}")

# Test 5: Paramètre URL api_key
print("\n📍 Test 5: Paramètre URL api_key...")
params = base_params.copy()
params['api_key'] = api_key
headers = {'Accept': 'application/json'}
response = requests.get(url, headers=headers, params=params)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print("   ✅ Méthode qui fonctionne!")
else:
    print(f"   ❌ Erreur: {response.json().get('message', response.text[:100])}")

# Test 6: Paramètre URL KEY (majuscules)
print("\n📍 Test 6: Paramètre URL KEY...")
params = base_params.copy()
params['KEY'] = api_key
headers = {'Accept': 'application/json'}
response = requests.get(url, headers=headers, params=params)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print("   ✅ Méthode qui fonctionne!")
else:
    print(f"   ❌ Erreur: {response.json().get('message', response.text[:100])}")

# Test 7: apikey header (minuscules)
print("\n📍 Test 7: apikey header...")
headers = {
    'apikey': api_key,
    'Accept': 'application/json'
}
response = requests.get(url, headers=headers, params=base_params)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print("   ✅ Méthode qui fonctionne!")
else:
    print(f"   ❌ Erreur: {response.json().get('message', response.text[:100])}")

print("\n" + "=" * 60)
print("\n💡 Si aucune méthode ne fonctionne:")
print("   1. Vérifiez que l'API Places est activée dans votre projet")
print("   2. Vérifiez les permissions de votre Service API Key")
print("   3. Consultez https://docs.foursquare.com/developer/reference/authentication")