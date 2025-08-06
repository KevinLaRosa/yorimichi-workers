#!/usr/bin/env python3
"""
Script pour vérifier le statut d'enrichissement des POIs
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
    
    # Client Supabase
    supabase: Client = create_client(supabase_url, supabase_key)
    
    print("\n" + "="*60)
    print("📊 STATUT D'ENRICHISSEMENT DES POIs")
    print("="*60)
    
    # Statistiques par statut
    statuses = ['pending', 'enriched', 'failed', 'no_match', 'skip']
    
    for status in statuses:
        try:
            result = supabase.table('locations').select('id', count='exact').eq('enrichment_status', status).execute()
            count = result.count
        except:
            # Si la colonne n'existe pas encore
            count = 0
            
        print(f"{status.upper():<12}: {count:>5} POIs")
    
    print("-"*60)
    
    # Total avec/sans FSQ ID
    total = supabase.table('locations').select('id', count='exact').execute()
    with_fsq = supabase.table('locations').select('id', count='exact').not_.is_('fsq_id', 'null').execute()
    without_fsq = supabase.table('locations').select('id', count='exact').is_('fsq_id', 'null').execute()
    
    print(f"TOTAL        : {total.count:>5} POIs")
    print(f"Avec FSQ ID  : {with_fsq.count:>5} ({with_fsq.count*100/total.count:.1f}%)")
    print(f"Sans FSQ ID  : {without_fsq.count:>5} ({without_fsq.count*100/total.count:.1f}%)")
    
    # POIs problématiques
    print("\n" + "="*60)
    print("🔴 POIs PROBLÉMATIQUES (failed ou no_match)")
    print("="*60)
    
    try:
        # Récupérer les POIs failed ou no_match
        problem_pois = supabase.table('locations') \
            .select('name, enrichment_status, enrichment_error, enrichment_attempts') \
            .in_('enrichment_status', ['failed', 'no_match']) \
            .limit(10) \
            .execute()
        
        if problem_pois.data:
            for poi in problem_pois.data:
                status = poi.get('enrichment_status', 'unknown')
                attempts = poi.get('enrichment_attempts', 0)
                error = poi.get('enrichment_error', 'N/A')[:50]
                print(f"• {poi['name'][:30]:<30} | {status:<10} | Tentatives: {attempts} | {error}")
        else:
            print("✅ Aucun POI problématique!")
    except Exception as e:
        if 'enrichment_status' in str(e):
            print("⚠️ Les colonnes de statut n'existent pas encore.")
            print("   Exécutez la migration SQL dans Supabase Dashboard d'abord.")
        else:
            print(f"Erreur: {e}")
    
    # POIs à traiter en priorité
    print("\n" + "="*60)
    print("🎯 PROCHAINES ACTIONS")
    print("="*60)
    
    try:
        # POIs sans tentative
        never_tried = supabase.table('locations') \
            .select('id', count='exact') \
            .is_('fsq_id', 'null') \
            .or_('enrichment_attempts.is.null,enrichment_attempts.eq.0') \
            .execute()
        
        # POIs failed avec peu de tentatives
        retry_candidates = supabase.table('locations') \
            .select('id', count='exact') \
            .in_('enrichment_status', ['failed', 'no_match']) \
            .lt('enrichment_attempts', 3) \
            .execute()
        
        print(f"1. Enrichir {without_fsq.count} POIs sans Foursquare ID")
        print(f"2. Réessayer {retry_candidates.count} POIs failed/no_match (<3 tentatives)")
        print(f"3. Vérifier/corriger {with_fsq.count} POIs avec FSQ ID")
        
    except:
        print(f"1. Enrichir {without_fsq.count} POIs sans Foursquare ID")
        print(f"2. Vérifier/corriger {with_fsq.count} POIs avec FSQ ID")
    
    print("="*60)


if __name__ == "__main__":
    main()