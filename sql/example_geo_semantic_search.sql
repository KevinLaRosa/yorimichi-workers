-- Exemple de requête combinant géolocalisation et recherche sémantique
-- "Je suis à Shibuya (35.6580, 139.7016), qu'est-ce que je peux faire avec mon enfant ?"

-- 1. D'abord trouver les POIs proches (dans un rayon de 2km)
WITH nearby_locations AS (
    SELECT 
        l.*,
        n.name as neighborhood_name,
        -- Calcul de distance en km (formule simplifiée pour Tokyo)
        SQRT(
            POW((l.latitude - 35.6580) * 111.32, 2) + 
            POW((l.longitude - 139.7016) * 91.52, 2)
        ) as distance_km
    FROM locations l
    LEFT JOIN neighborhoods n ON l.neighborhood_id = n.id
    WHERE l.latitude IS NOT NULL 
    AND l.longitude IS NOT NULL
    AND l.is_active = true
    -- Filtre approximatif pour optimiser (carré de 2km)
    AND l.latitude BETWEEN 35.6580 - 0.018 AND 35.6580 + 0.018
    AND l.longitude BETWEEN 139.7016 - 0.022 AND 139.7016 + 0.022
),
-- 2. Filtrer par distance réelle et tags famille
family_friendly_nearby AS (
    SELECT DISTINCT nl.*
    FROM nearby_locations nl
    JOIN location_tags lt ON nl.id = lt.location_id
    JOIN tags t ON lt.tag_id = t.id
    WHERE nl.distance_km <= 2  -- Dans un rayon de 2km
    AND (
        t.name = 'Family Friendly' 
        OR t.name = 'Kid Friendly'
        OR nl.features->>'visitor_types' LIKE '%family%'
    )
)
-- 3. Ensuite faire la recherche sémantique sur ces POIs proches
SELECT 
    name,
    neighborhood_name,
    ROUND(distance_km::numeric, 2) || ' km' as distance,
    summary,
    -- Score combiné (distance + pertinence sémantique)
    ROUND((1 - distance_km/2)::numeric * 0.5 + 0.5, 2) as combined_score
FROM family_friendly_nearby
ORDER BY distance_km
LIMIT 5;

-- Version avec embedding pour "fun activities for kids"
-- L'agent générerait l'embedding pour cette requête et l'utiliserait
-- pour trouver les activités les plus pertinentes sémantiquement