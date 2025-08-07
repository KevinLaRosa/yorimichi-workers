#!/usr/bin/env python3
"""
Script simple pour supprimer les doublons de la base de données
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime

# Charger les variables d'environnement
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

def main():
    # Configuration Supabase
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ Variables d'environnement Supabase manquantes")
        sys.exit(1)
    
    # Client Supabase avec Service Role Key (pas de RLS)
    supabase: Client = create_client(supabase_url, supabase_key)
    
    print("\n" + "="*60)
    print("🗑️ SUPPRESSION SIMPLE DES DOUBLONS")
    print("="*60)
    
    # 1. Récupérer tous les doublons
    duplicates = supabase.table('locations').select('*').eq('enrichment_status', 'duplicate').execute()
    print(f"\n📊 Total doublons trouvés: {len(duplicates.data)}")
    
    if not duplicates.data:
        print("✅ Aucun doublon à supprimer!")
        return
    
    # 2. Confirmer la suppression
    print("\n⚠️ ATTENTION: Cette action va supprimer définitivement ces POIs")
    print("Les premiers 10 doublons:")
    for i, dup in enumerate(duplicates.data[:10], 1):
        print(f"  {i}. {dup['name']}")
    
    if len(duplicates.data) > 10:
        print(f"  ... et {len(duplicates.data) - 10} autres")
    
    confirm = input("\nVoulez-vous vraiment supprimer tous ces doublons? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("Annulé")
        return
    
    # 3. Supprimer un par un avec gestion d'erreur
    deleted = 0
    errors = 0
    
    print("\n🔄 Suppression en cours...")
    for dup in duplicates.data:
        try:
            # Utiliser l'ID directement dans la requête de suppression
            poi_id = dup['id']
            poi_name = dup['name']
            
            # Supprimer avec eq() au lieu de match()
            result = supabase.table('locations').delete().eq('id', poi_id).execute()
            
            # Vérifier si la suppression a réussi
            if result.data:
                deleted += 1
                print(f"  ✅ Supprimé: {poi_name}")
            else:
                errors += 1
                print(f"  ⚠️ Pas supprimé (déjà absent?): {poi_name}")
                
        except Exception as e:
            errors += 1
            print(f"  ❌ Erreur pour {dup['name']}: {str(e)[:100]}")
    
    # 4. Résumé
    print("\n" + "="*60)
    print("📊 RÉSUMÉ")
    print("="*60)
    print(f"Total traités: {len(duplicates.data)}")
    print(f"✅ Supprimés: {deleted}")
    print(f"❌ Erreurs: {errors}")
    
    if deleted > 0:
        print(f"\n✨ {deleted} doublons ont été supprimés avec succès!")


if __name__ == "__main__":
    main()