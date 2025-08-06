#!/usr/bin/env python3
"""
Test de connexion avec le SDK Supabase (plus simple!)
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Charger les variables d'environnement
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

print("🔍 Test avec SDK Supabase")
print("=" * 60)

# Configuration
supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY') or os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')

if not supabase_url or not supabase_key:
    print("❌ Variables manquantes")
    sys.exit(1)

print(f"📋 URL: {supabase_url}")
print(f"🔑 Using key: {'SERVICE_ROLE' if 'service_role' in supabase_key else 'ANON'}")

# Créer le client
supabase: Client = create_client(supabase_url, supabase_key)

try:
    # Test 1: Compter les POIs
    result = supabase.table('locations').select('id', count='exact').execute()
    print(f"\n✅ Connexion réussie!")
    print(f"📊 {result.count} POIs dans la base")
    
    # Test 2: Récupérer 5 POIs
    pois = supabase.table('locations').select('id,name,fsq_id').limit(5).execute()
    print(f"\n📍 Exemple de POIs:")
    for poi in pois.data:
        enriched = "✅" if poi.get('fsq_id') else "❌"
        print(f"   {enriched} {poi['name'][:50]}")
    
    # Test 3: Compter les POIs à enrichir
    to_enrich = supabase.table('locations').select('id', count='exact').is_('fsq_id', 'null').execute()
    print(f"\n📈 POIs à enrichir: {to_enrich.count}")
    
    # Test 4: Vérifier le bucket storage
    buckets = supabase.storage.list_buckets()
    print(f"\n📦 Buckets Storage:")
    for bucket in buckets:
        print(f"   - {bucket['name']} ({'public' if bucket.get('public') else 'private'})")
    
    print("\n🎉 SDK Supabase fonctionne parfaitement!")
    print("   On peut utiliser le SDK pour toutes les opérations!")
    
except Exception as e:
    print(f"\n❌ Erreur: {e}")
    print("\n💡 Vérifiez que vous utilisez SUPABASE_SERVICE_ROLE_KEY")
    print("   (pas SUPABASE_ANON_KEY pour les opérations d'écriture)")