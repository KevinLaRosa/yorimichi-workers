#!/bin/bash

# Script simple pour tester la recherche sémantique via l'API Supabase

echo "🔍 Test de recherche sémantique Yorimichi"
echo "========================================"

# Charger les variables d'environnement
source .env.local

# Requête de test
SEARCH_QUERY="peaceful temple with garden in Tokyo"
echo "Query: $SEARCH_QUERY"
echo

# 1. Générer l'embedding avec OpenAI
echo "📊 Génération de l'embedding..."
EMBEDDING_RESPONSE=$(curl -s https://api.openai.com/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "text-embedding-ada-002",
    "input": "'"$SEARCH_QUERY"'"
  }')

# Extraire l'embedding (utilise jq si disponible, sinon affiche le résultat brut)
if command -v jq &> /dev/null; then
    EMBEDDING=$(echo $EMBEDDING_RESPONSE | jq -c '.data[0].embedding')
    echo "✅ Embedding généré"
else
    echo "⚠️  jq non installé - affichage du résultat brut"
    echo $EMBEDDING_RESPONSE | head -c 200
    echo "..."
    exit 1
fi

# 2. Recherche dans Supabase
echo
echo "🔎 Recherche dans la base de données..."
curl -s "$NEXT_PUBLIC_SUPABASE_URL/rest/v1/rpc/match_locations" \
  -H "apikey: $NEXT_PUBLIC_SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $NEXT_PUBLIC_SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query_embedding": '"$EMBEDDING"',
    "match_threshold": 0.5,
    "match_count": 5
  }' | jq '.[0:3] | .[] | {name, similarity, summary, neighborhood_name}'

echo
echo "✅ Test terminé!"