-- Script de configuration de la base de données pour Yorimichi Intelligent Crawler V2
-- À exécuter dans votre projet Supabase avant de lancer le crawler

-- Table pour le suivi des URLs traitées (idempotence et reprise sur erreur)
CREATE TABLE IF NOT EXISTS processed_urls (
  url TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'skipped_not_a_poi', 'skipped_duplicate')),
  processed_at TIMESTAMPTZ DEFAULT now(),
  error_details TEXT -- Optionnel: pour stocker les détails d'erreur
);

-- Index pour améliorer les performances de recherche
CREATE INDEX idx_processed_urls_status ON processed_urls(status);
CREATE INDEX idx_processed_urls_processed_at ON processed_urls(processed_at);

-- Table pour les logs des agents (monitoring et debugging)
CREATE TABLE IF NOT EXISTS agent_logs (
  id BIGSERIAL PRIMARY KEY,
  agent_name TEXT NOT NULL DEFAULT 'Intelligent Crawler',
  status TEXT NOT NULL CHECK (status IN ('STARTED', 'RUNNING', 'SUCCESS', 'ERROR')),
  message TEXT,
  details JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Index pour les requêtes de monitoring
CREATE INDEX idx_agent_logs_agent_name ON agent_logs(agent_name);
CREATE INDEX idx_agent_logs_status ON agent_logs(status);
CREATE INDEX idx_agent_logs_created_at ON agent_logs(created_at DESC);

-- Fonction pour nettoyer les vieux logs (optionnel)
CREATE OR REPLACE FUNCTION cleanup_old_logs()
RETURNS void AS $$
BEGIN
  DELETE FROM agent_logs 
  WHERE created_at < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Exemple de fonction match_locations pour la recherche vectorielle
-- Note: Assurez-vous d'avoir activé l'extension pgvector dans votre projet Supabase
CREATE OR REPLACE FUNCTION match_locations(
  query_embedding vector(1536),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  id uuid,
  name text,
  description text,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    l.id,
    l.name,
    l.description,
    1 - (l.embedding <=> query_embedding) as similarity
  FROM locations l
  WHERE 1 - (l.embedding <=> query_embedding) > match_threshold
  ORDER BY l.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;