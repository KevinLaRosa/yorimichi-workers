-- Script de setup rapide pour Supabase
-- À exécuter dans l'éditeur SQL de Supabase

-- Table pour tracker les URLs déjà traitées
CREATE TABLE IF NOT EXISTS processed_urls (
  url TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  processed_at TIMESTAMPTZ DEFAULT now(),
  error_details TEXT
);

-- Index pour performance
CREATE INDEX IF NOT EXISTS idx_processed_urls_status ON processed_urls(status);

-- Table pour les logs (optionnel mais utile)
CREATE TABLE IF NOT EXISTS agent_logs (
  id BIGSERIAL PRIMARY KEY,
  agent_name TEXT NOT NULL DEFAULT 'Crawler',
  status TEXT NOT NULL,
  message TEXT,
  details JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Fonction de recherche par similarité
-- Note: Adaptée pour utiliser 'search_locations' si elle existe
CREATE OR REPLACE FUNCTION match_locations(
  query_embedding vector(1536),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  id uuid,
  name text,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  -- Si vous avez déjà une fonction search_locations, utilisez-la
  -- Sinon, voici une implémentation basique
  RETURN QUERY
  SELECT 
    l.id,
    l.name,
    1 - (l.embedding <=> query_embedding) as similarity
  FROM locations l
  WHERE l.embedding IS NOT NULL
    AND 1 - (l.embedding <=> query_embedding) > match_threshold
  ORDER BY l.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;