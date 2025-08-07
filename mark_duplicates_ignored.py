#!/usr/bin/env python3
"""
Script pour marquer les doublons comme 'ignored' au lieu de les supprimer
Solution pragmatique pour contourner le problème de trigger/RLS
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client

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
        sys.exit(1)
    
    # Client Supabase avec Service Role Key
    supabase = create_client(supabase_url, service_role_key)
    
    print("\n" + "="*60)
    print("🏷️ MARQUAGE DES DOUBLONS COMME IGNORÉS")
    print("="*60)
    
    # 1. Compter les doublons
    duplicates = supabase.table('locations').select('name').eq('enrichment_status', 'duplicate').execute()
    total = len(duplicates.data)
    
    if total == 0:
        print("✅ Aucun doublon à traiter!")
        return
    
    print(f"\n📊 {total} doublons trouvés")
    print("\nExemples:")
    for i, dup in enumerate(duplicates.data[:10], 1):
        print(f"  {i}. {dup['name']}")
    
    if total > 10:
        print(f"  ... et {total - 10} autres")
    
    print("\n⚠️ Ces POIs seront marqués comme 'ignored'")
    print("Ils ne seront plus traités par les scripts d'enrichissement")
    print("mais resteront dans la base de données.")
    
    # 2. Confirmer
    confirm = input("\nVoulez-vous continuer? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("Annulé")
        return
    
    # 3. Marquer comme ignored
    print("\n🔄 Marquage en cours...")
    
    try:
        result = supabase.table('locations').update({
            'enrichment_status': 'ignored',
            'enrichment_error': 'Doublon FSQ ID - POI ignoré pour éviter les conflits'
        }).eq('enrichment_status', 'duplicate').execute()
        
        updated = len(result.data)
        
        print(f"\n✅ {updated} doublons marqués comme 'ignored'")
        print("\nCes POIs:")
        print("  • Ne seront plus traités par enrich_all_pois_sdk.py")
        print("  • Restent dans la base mais sont exclus des processus")
        print("  • Peuvent être supprimés manuellement depuis Supabase Dashboard si nécessaire")
        
        # 4. Afficher le statut global
        print("\n📊 Statut des POIs après marquage:")
        
        # Compter les différents statuts
        for status in ['pending', 'enriched', 'failed', 'no_match', 'ignored']:
            count_result = supabase.table('locations').select('id', count='exact').eq('enrichment_status', status).execute()
            print(f"  • {status}: {count_result.count}")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return
    
    print("\n" + "="*60)
    print("✨ Terminé! Vous pouvez maintenant relancer l'enrichissement:")
    print("   python3 enrich_all_pois_sdk.py")
    print("="*60)


if __name__ == "__main__":
    main()