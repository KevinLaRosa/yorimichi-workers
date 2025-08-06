-- Migration pour ajouter le support des adresses en romaji
-- À exécuter dans Supabase Dashboard > SQL Editor

-- 1. Ajouter la colonne address_romaji pour stocker l'adresse en caractères latins
ALTER TABLE locations
ADD COLUMN IF NOT EXISTS address_romaji TEXT;

-- 2. Ajouter un commentaire pour documenter l'usage de la colonne
COMMENT ON COLUMN locations.address_romaji IS 'Adresse en caractères romains (latins) pour faciliter la lecture internationale';

-- 3. Créer un index pour améliorer les performances de recherche
CREATE INDEX IF NOT EXISTS idx_locations_address_romaji 
ON locations(address_romaji) 
WHERE address_romaji IS NOT NULL;

-- 4. Optionnel: Ajouter une colonne pour marquer si la traduction a été faite
ALTER TABLE locations
ADD COLUMN IF NOT EXISTS romaji_translated_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN locations.romaji_translated_at IS 'Date et heure de la traduction en romaji';

-- Vérification
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'locations' 
AND column_name IN ('address_romaji', 'romaji_translated_at')
ORDER BY ordinal_position;