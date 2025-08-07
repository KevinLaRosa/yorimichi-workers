#!/usr/bin/env python3
"""
Script de diagnostic pour comprendre pourquoi les suppressions échouent
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client
import requests

# Charger les variables d'environnement
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

def main():
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url or not service_role_key:
        print("❌ Variables d'environnement manquantes")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("🔍 DIAGNOSTIC DES PROBLÈMES DE SUPPRESSION")
    print("="*60)
    
    # Headers pour l'API REST avec Service Role
    headers = {
        'apikey': service_role_key,
        'Authorization': f'Bearer {service_role_key}',
        'Content-Type': 'application/json'
    }
    
    # 1. Vérifier les politiques RLS
    print("\n📋 Vérification des politiques RLS...")
    rls_url = f"{supabase_url}/rest/v1/rpc/get_policies"
    
    # 2. Essayer différentes méthodes de suppression
    print("\n🧪 Test de différentes méthodes de suppression...")
    
    # Récupérer un doublon pour tester
    test_url = f"{supabase_url}/rest/v1/locations?enrichment_status=eq.duplicate&limit=1"
    response = requests.get(test_url, headers=headers)
    
    if response.status_code == 200 and response.json():
        test_poi = response.json()[0]
        print(f"\nPOI de test: {test_poi['name']} (ID: {test_poi['id']})")
        
        # Méthode 1: UPDATE au lieu de DELETE
        print("\n1️⃣ Test UPDATE enrichment_status -> 'deleted'...")
        update_url = f"{supabase_url}/rest/v1/locations?id=eq.{test_poi['id']}"
        update_data = {
            'enrichment_status': 'deleted',
            'enrichment_error': 'Marqué pour suppression'
        }
        
        response = requests.patch(update_url, headers=headers, json=update_data)
        if response.status_code in [200, 204]:
            print("   ✅ UPDATE fonctionne! On peut marquer comme 'deleted'")
            
            # Remettre en duplicate pour les autres tests
            update_data = {'enrichment_status': 'duplicate'}
            requests.patch(update_url, headers=headers, json=update_data)
        else:
            print(f"   ❌ UPDATE échoué: {response.status_code}")
            print(f"   Détails: {response.text[:200]}")
        
        # Méthode 2: Essayer avec une fonction RPC
        print("\n2️⃣ Test suppression via fonction RPC...")
        print("   ℹ️ Nécessite de créer une fonction dans Supabase")
        
    else:
        print("Aucun doublon trouvé pour les tests")
    
    # 3. Proposer des solutions
    print("\n" + "="*60)
    print("💡 SOLUTIONS RECOMMANDÉES")
    print("="*60)
    
    print("""
1. SOLUTION IMMÉDIATE (Contournement):
   Marquer les doublons comme 'deleted' ou 'ignored' au lieu de les supprimer
   
2. SOLUTION DANS SUPABASE DASHBOARD:
   a) Aller dans SQL Editor
   b) Exécuter: SELECT * FROM pg_trigger WHERE tgrelid = 'locations'::regclass;
   c) Identifier le trigger problématique
   d) Le corriger ou le désactiver temporairement
   
3. SOLUTION PAR FONCTION SQL:
   Créer une fonction qui supprime sans déclencher les triggers:
   
   CREATE OR REPLACE FUNCTION delete_duplicates()
   RETURNS void AS $$
   BEGIN
     DELETE FROM locations WHERE enrichment_status = 'duplicate';
   END;
   $$ LANGUAGE plpgsql SECURITY DEFINER;
   
4. SOLUTION PRAGMATIQUE:
   Utiliser le script mark_duplicates_ignored.py (voir ci-dessous)
""")


if __name__ == "__main__":
    main()