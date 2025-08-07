#!/usr/bin/env python3
"""
Script pour analyser et nettoyer les doublons dans la base de données
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime
import argparse

# Charger les variables d'environnement
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

def main():
    parser = argparse.ArgumentParser(description='Analyser et nettoyer les doublons')
    parser.add_argument('--delete', action='store_true', help='Supprimer les doublons (garder l\'original)')
    parser.add_argument('--merge', action='store_true', help='Fusionner les données des doublons')
    args = parser.parse_args()
    
    # Configuration Supabase
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ Variables d'environnement Supabase manquantes")
        sys.exit(1)
    
    # Client Supabase
    supabase: Client = create_client(supabase_url, supabase_key)
    
    print("\n" + "="*60)
    print("🔍 ANALYSE DES DOUBLONS")
    print("="*60)
    
    # 1. Récupérer tous les doublons
    duplicates = supabase.table('locations').select('*').eq('enrichment_status', 'duplicate').execute()
    print(f"\n📊 Total doublons marqués: {len(duplicates.data)}")
    
    if not duplicates.data:
        print("✅ Aucun doublon trouvé!")
        return
    
    # 2. Analyser chaque doublon pour trouver l'original
    duplicate_pairs = []
    
    for dup in duplicates.data:
        # Extraire le fsq_id du message d'erreur
        error_msg = dup.get('enrichment_error', '')
        if 'Key (fsq_id)=' in error_msg:
            # Extraire le fsq_id
            fsq_id = error_msg.split('Key (fsq_id)=(')[1].split(')')[0]
            
            # Trouver l'original avec ce fsq_id
            original = supabase.table('locations').select('*').eq('fsq_id', fsq_id).execute()
            
            if original.data:
                duplicate_pairs.append({
                    'duplicate': dup,
                    'original': original.data[0],
                    'fsq_id': fsq_id
                })
    
    print(f"\n🔗 Paires trouvées: {len(duplicate_pairs)}")
    
    # 3. Afficher l'analyse
    print("\n" + "="*60)
    print("📋 DÉTAIL DES DOUBLONS")
    print("="*60)
    
    for i, pair in enumerate(duplicate_pairs[:20], 1):  # Limiter à 20 pour l'affichage
        dup = pair['duplicate']
        orig = pair['original']
        
        print(f"\n{i}. FSQ ID: {pair['fsq_id']}")
        print(f"   ORIGINAL : {orig['name']}")
        if orig.get('address'):
            print(f"             {orig['address']}")
        print(f"   DOUBLON  : {dup['name']}")
        if dup.get('address'):
            print(f"             {dup['address']}")
        
        # Vérifier quelles données le doublon a que l'original n'a pas
        unique_data = []
        if dup.get('description') and not orig.get('description'):
            unique_data.append('description')
        if dup.get('website') and not orig.get('website'):
            unique_data.append('website')
        if dup.get('phone') and not orig.get('phone'):
            unique_data.append('phone')
        
        if unique_data:
            print(f"   ⚠️ Le doublon a des données uniques: {', '.join(unique_data)}")
    
    if len(duplicate_pairs) > 20:
        print(f"\n... et {len(duplicate_pairs) - 20} autres paires")
    
    # 4. Statistiques
    print("\n" + "="*60)
    print("📊 STATISTIQUES")
    print("="*60)
    
    # Doublons par source
    sources = {}
    for dup in duplicates.data:
        source = dup.get('source', 'unknown')
        sources[source] = sources.get(source, 0) + 1
    
    print("\nPar source:")
    for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        print(f"  {source}: {count}")
    
    # 5. Actions proposées
    print("\n" + "="*60)
    print("🎯 ACTIONS RECOMMANDÉES")
    print("="*60)
    
    if args.delete:
        print("\n⚠️ MODE SUPPRESSION ACTIVÉ")
        confirm = input("Voulez-vous vraiment supprimer tous les doublons? (yes/no): ")
        
        if confirm.lower() == 'yes':
            deleted = 0
            for pair in duplicate_pairs:
                try:
                    # Supprimer le doublon
                    supabase.table('locations').delete().eq('id', pair['duplicate']['id']).execute()
                    deleted += 1
                    print(f"  ✅ Supprimé: {pair['duplicate']['name']}")
                except Exception as e:
                    print(f"  ❌ Erreur suppression {pair['duplicate']['name']}: {e}")
            
            print(f"\n✅ {deleted} doublons supprimés")
            
    elif args.merge:
        print("\n🔄 MODE FUSION ACTIVÉ")
        print("Cette fonctionnalité va fusionner les données uniques des doublons dans les originaux")
        confirm = input("Voulez-vous continuer? (yes/no): ")
        
        if confirm.lower() == 'yes':
            merged = 0
            for pair in duplicate_pairs:
                dup = pair['duplicate']
                orig = pair['original']
                updates = {}
                
                # Fusionner les données
                if dup.get('description') and not orig.get('description'):
                    updates['description'] = dup['description']
                if dup.get('website') and not orig.get('website'):
                    updates['website'] = dup['website']
                if dup.get('phone') and not orig.get('phone'):
                    updates['phone'] = dup['phone']
                if dup.get('address') and not orig.get('address'):
                    updates['address'] = dup['address']
                
                if updates:
                    try:
                        # Mettre à jour l'original
                        supabase.table('locations').update(updates).eq('id', orig['id']).execute()
                        # Supprimer le doublon
                        supabase.table('locations').delete().eq('id', dup['id']).execute()
                        merged += 1
                        print(f"  ✅ Fusionné: {dup['name']} -> {orig['name']}")
                    except Exception as e:
                        print(f"  ❌ Erreur fusion {dup['name']}: {e}")
                else:
                    # Pas de données à fusionner, juste supprimer
                    try:
                        supabase.table('locations').delete().eq('id', dup['id']).execute()
                        merged += 1
                        print(f"  ✅ Supprimé (pas de données uniques): {dup['name']}")
                    except Exception as e:
                        print(f"  ❌ Erreur suppression {dup['name']}: {e}")
            
            print(f"\n✅ {merged} doublons traités")
    else:
        print("\nOptions disponibles:")
        print("  --delete : Supprimer tous les doublons (garder seulement les originaux)")
        print("  --merge  : Fusionner les données uniques puis supprimer les doublons")
        print("\nExemple:")
        print("  python3 analyze_duplicates.py          # Juste analyser")
        print("  python3 analyze_duplicates.py --merge  # Fusionner et supprimer")
        print("  python3 analyze_duplicates.py --delete # Supprimer directement")
    
    print("="*60)


if __name__ == "__main__":
    main()