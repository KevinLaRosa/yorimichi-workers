#!/usr/bin/env python3
"""
Script pour supprimer les doublons en contournant les politiques RLS
en utilisant la Service Role Key et une requête RPC
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
import requests

# Charger les variables d'environnement
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

def main():
    # Configuration Supabase
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url or not service_role_key:
        print("❌ Variables d'environnement Supabase manquantes")
        print("Vérifiez NEXT_PUBLIC_SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("🗑️ SUPPRESSION DES DOUBLONS (Service Role)")
    print("="*60)
    
    # Utiliser l'API REST directement avec la Service Role Key
    headers = {
        'apikey': service_role_key,
        'Authorization': f'Bearer {service_role_key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }
    
    # 1. Récupérer les doublons
    url = f"{supabase_url}/rest/v1/locations"
    params = {
        'enrichment_status': 'eq.duplicate',
        'select': 'id,name'
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"❌ Erreur lors de la récupération: {response.text}")
        return
    
    duplicates = response.json()
    print(f"\n📊 Total doublons trouvés: {len(duplicates)}")
    
    if not duplicates:
        print("✅ Aucun doublon à supprimer!")
        return
    
    # 2. Afficher les exemples
    print("\nExemples de doublons à supprimer:")
    for i, dup in enumerate(duplicates[:10], 1):
        print(f"  {i}. {dup['name']}")
    
    if len(duplicates) > 10:
        print(f"  ... et {len(duplicates) - 10} autres")
    
    # 3. Confirmer
    confirm = input("\nVoulez-vous vraiment supprimer tous ces doublons? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("Annulé")
        return
    
    # 4. Supprimer un par un
    deleted = 0
    errors = 0
    
    print("\n🔄 Suppression en cours...")
    for dup in duplicates:
        try:
            # Supprimer via l'API REST avec Service Role
            delete_url = f"{supabase_url}/rest/v1/locations?id=eq.{dup['id']}"
            
            response = requests.delete(delete_url, headers=headers)
            
            if response.status_code in [200, 204]:
                deleted += 1
                print(f"  ✅ Supprimé: {dup['name']}")
            else:
                errors += 1
                print(f"  ❌ Erreur pour {dup['name']}: {response.status_code}")
                if response.text:
                    print(f"     Détails: {response.text[:100]}")
                
        except Exception as e:
            errors += 1
            print(f"  ❌ Exception pour {dup['name']}: {str(e)[:100]}")
    
    # 5. Résumé
    print("\n" + "="*60)
    print("📊 RÉSUMÉ")
    print("="*60)
    print(f"Total traités: {len(duplicates)}")
    print(f"✅ Supprimés: {deleted}")
    print(f"❌ Erreurs: {errors}")
    
    if deleted > 0:
        print(f"\n✨ {deleted} doublons ont été supprimés avec succès!")


if __name__ == "__main__":
    main()