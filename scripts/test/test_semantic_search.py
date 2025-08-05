#!/usr/bin/env python3
"""
Test de recherche sémantique pour vérifier que les embeddings fonctionnent
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client
import openai
from openai import OpenAI

# Charger les variables d'environnement
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

# Clients
supabase = create_client(
    os.getenv('NEXT_PUBLIC_SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_ROLE_KEY')
)

openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def test_semantic_search(query: str, match_count: int = 5):
    """Test la recherche sémantique avec une requête"""
    print(f"\n🔍 Recherche sémantique pour: '{query}'")
    print("="*60)
    
    try:
        # 1. Générer l'embedding pour la requête
        print("📊 Génération de l'embedding de la requête...")
        embedding_response = openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=query
        )
        query_embedding = embedding_response.data[0].embedding
        print(f"✅ Embedding généré: {len(query_embedding)} dimensions")
        
        # 2. Recherche sémantique via la fonction RPC
        print(f"\n🔎 Recherche des {match_count} meilleurs résultats...")
        results = supabase.rpc('match_locations', {
            'query_embedding': query_embedding,
            'match_threshold': 0.5,  # Seuil bas pour voir plus de résultats
            'match_count': match_count
        }).execute()
        
        if not results.data:
            print("❌ Aucun résultat trouvé")
            return
            
        print(f"✅ {len(results.data)} résultats trouvés!\n")
        
        # 3. Afficher les résultats
        for idx, location in enumerate(results.data, 1):
            similarity = location.get('similarity', 0)
            print(f"{idx}. {location['name']}")
            print(f"   📍 Quartier: {location.get('neighborhood_name', 'Non spécifié')}")
            print(f"   🎯 Similarité: {similarity:.2%}")
            print(f"   📝 {location['summary']}")
            print(f"   🔗 {location.get('source_url', 'N/A')}")
            print()
            
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()

def test_various_queries():
    """Test avec différentes requêtes touristiques"""
    queries = [
        "romantic date spot in Tokyo",
        "best ramen restaurant",
        "temple with garden peaceful",
        "fun activities for families with kids",
        "traditional Japanese experience",
        "cheap food budget traveler",
        "rainy day indoor activities",
        "photography spots Instagram worthy"
    ]
    
    print("\n🚀 TEST DE RECHERCHE SÉMANTIQUE YORIMICHI")
    print("="*60)
    
    for query in queries:
        test_semantic_search(query, match_count=3)
        print("\n" + "-"*60 + "\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Test avec une requête personnalisée
        query = " ".join(sys.argv[1:])
        test_semantic_search(query)
    else:
        # Test avec plusieurs requêtes prédéfinies
        test_various_queries()