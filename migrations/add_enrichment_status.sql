-- Migration pour ajouter le tracking du statut d'enrichissement
-- À exécuter dans Supabase Dashboard > SQL Editor

-- 1. Ajouter les colonnes de statut
ALTER TABLE locations
ADD COLUMN IF NOT EXISTS enrichment_status TEXT DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS enrichment_error TEXT,
ADD COLUMN IF NOT EXISTS enrichment_attempts INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_enrichment_attempt TIMESTAMP WITH TIME ZONE;

-- 2. Ajouter une contrainte pour les valeurs valides
ALTER TABLE locations
ADD CONSTRAINT enrichment_status_check 
CHECK (enrichment_status IN ('pending', 'enriched', 'failed', 'no_match', 'skip'));

-- 3. Ajouter des commentaires pour documenter
COMMENT ON COLUMN locations.enrichment_status IS 'Statut enrichissement: pending|enriched|failed|no_match|skip';
COMMENT ON COLUMN locations.enrichment_error IS 'Message d''erreur si échec';
COMMENT ON COLUMN locations.enrichment_attempts IS 'Nombre de tentatives d''enrichissement';
COMMENT ON COLUMN locations.last_enrichment_attempt IS 'Date/heure de la dernière tentative';

-- 4. Créer un index pour les requêtes de statut
CREATE INDEX IF NOT EXISTS idx_locations_enrichment_status 
ON locations(enrichment_status) 
WHERE enrichment_status IN ('failed', 'no_match');

-- 5. Mettre à jour les POIs déjà enrichis
UPDATE locations 
SET enrichment_status = 'enriched',
    enrichment_attempts = 1
WHERE fsq_id IS NOT NULL;

-- 6. Vérification
SELECT 
    enrichment_status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as percentage
FROM locations
GROUP BY enrichment_status
ORDER BY count DESC;