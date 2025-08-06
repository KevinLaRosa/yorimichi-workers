#!/usr/bin/env python3
"""
Script de migration pour ajouter les colonnes Foursquare manquantes
Selon le plan TODO_YORIMICHI.md Phase 3
"""

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
import psycopg2

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

def migrate_database():
    """Ajoute les colonnes manquantes pour Foursquare"""
    
    # Configuration DB
    supabase_url = os.getenv('SUPABASE_URL')
    if not supabase_url:
        logger.error("SUPABASE_URL non définie!")
        sys.exit(1)
        
    project_id = supabase_url.replace('https://', '').split('.')[0]
    
    conn = psycopg2.connect(
        host=f"{project_id}.pooler.supabase.com",
        database='postgres',
        user=f"postgres.{project_id}",
        password=os.getenv('SUPABASE_DB_PASSWORD'),
        port=6543
    )
    
    cursor = conn.cursor()
    
    # Liste des colonnes à ajouter
    columns_to_add = [
        # Identifiants externes
        ("fsq_id", "VARCHAR(50) UNIQUE", "Foursquare ID"),
        # Note: google_place_id existe déjà
        
        # Métriques et évaluations
        ("rating", "DECIMAL(3,1)", "Rating Foursquare sur 10"),
        ("price_tier", "INTEGER CHECK (price_tier BETWEEN 1 AND 4)", "Niveau de prix 1-4"),
        ("popularity", "DECIMAL(3,2)", "Score de popularité"),
        ("verified", "BOOLEAN DEFAULT FALSE", "Statut vérifié Foursquare"),
        
        # Données structurées (certaines existent déjà)
        ("photos", "JSONB DEFAULT '[]'::jsonb", "Photos structurées avec URLs"),
        ("hours", "JSONB", "Horaires Foursquare structurés"),
        ("stats", "JSONB", "Statistiques Foursquare"),
        ("tips", "JSONB DEFAULT '[]'::jsonb", "Tips/Avis Foursquare"),
        
        # Contact et social (certains existent)
        # phone et website existent déjà
        ("social_links", "JSONB", "Liens réseaux sociaux"),
        
        # Métadonnées
        ("tastes", "TEXT[]", "Tags de goûts/styles"),
        ("amenities", "TEXT[]", "Équipements disponibles"),
        ("payment_methods_array", "TEXT[]", "Méthodes de paiement acceptées"),
        
        # Foursquare spécifique
        ("fsq_categories", "TEXT[]", "Catégories Foursquare"),
        ("fsq_chain_name", "VARCHAR(255)", "Nom de la chaîne si applicable"),
        ("fsq_chain_id", "VARCHAR(50)", "ID de la chaîne"),
        
        # Horaires détaillés
        ("hours_popular", "JSONB", "Heures d'affluence"),
        ("hours_display", "TEXT", "Horaires format texte"),
        
        # Enrichissement timestamps
        ("fsq_enriched_at", "TIMESTAMP WITH TIME ZONE", "Date d'enrichissement Foursquare"),
        ("photos_processed_at", "TIMESTAMP WITH TIME ZONE", "Date de traitement des photos")
    ]
    
    logger.info("🔄 Début de la migration de la base de données")
    
    added_count = 0
    skipped_count = 0
    
    for column_name, column_type, description in columns_to_add:
        try:
            # Vérifier si la colonne existe
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'locations' 
                AND column_name = %s
            """, (column_name,))
            
            if cursor.fetchone():
                logger.info(f"⏭️  Colonne '{column_name}' existe déjà")
                skipped_count += 1
            else:
                # Ajouter la colonne
                query = f"ALTER TABLE locations ADD COLUMN {column_name} {column_type}"
                cursor.execute(query)
                
                # Ajouter un commentaire si disponible
                if description:
                    comment_query = f"COMMENT ON COLUMN locations.{column_name} IS %s"
                    cursor.execute(comment_query, (description,))
                
                conn.commit()
                logger.info(f"✅ Colonne ajoutée: {column_name} ({column_type})")
                added_count += 1
                
        except Exception as e:
            logger.error(f"❌ Erreur pour colonne {column_name}: {e}")
            conn.rollback()
    
    # Créer les index pour performance
    indexes = [
        ("idx_locations_fsq_id", "fsq_id", "Index sur Foursquare ID"),
        ("idx_locations_rating", "rating", "Index sur rating pour tri"),
        ("idx_locations_price_tier", "price_tier", "Index sur niveau de prix"),
        ("idx_locations_verified", "verified", "Index sur statut vérifié"),
        ("idx_locations_fsq_enriched", "fsq_enriched_at", "Index sur date enrichissement")
    ]
    
    logger.info("\n📇 Création des index...")
    
    for index_name, column, description in indexes:
        try:
            # Vérifier si l'index existe
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'locations' 
                AND indexname = %s
            """, (index_name,))
            
            if cursor.fetchone():
                logger.info(f"⏭️  Index '{index_name}' existe déjà")
            else:
                # Vérifier d'abord si la colonne existe
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'locations' 
                    AND column_name = %s
                """, (column,))
                
                if cursor.fetchone():
                    query = f"CREATE INDEX {index_name} ON locations({column})"
                    cursor.execute(query)
                    conn.commit()
                    logger.info(f"✅ Index créé: {index_name} sur {column}")
                else:
                    logger.warning(f"⚠️  Colonne '{column}' n'existe pas, index non créé")
                    
        except Exception as e:
            logger.error(f"❌ Erreur création index {index_name}: {e}")
            conn.rollback()
    
    # Index GIN pour JSONB
    gin_indexes = [
        ("idx_locations_hours_gin", "hours", "GIN index sur horaires"),
        ("idx_locations_photos_gin", "photos", "GIN index sur photos"),
        ("idx_locations_stats_gin", "stats", "GIN index sur stats")
    ]
    
    logger.info("\n🔍 Création des index GIN pour JSONB...")
    
    for index_name, column, description in gin_indexes:
        try:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'locations' 
                AND indexname = %s
            """, (index_name,))
            
            if cursor.fetchone():
                logger.info(f"⏭️  Index GIN '{index_name}' existe déjà")
            else:
                # Vérifier si la colonne existe
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'locations' 
                    AND column_name = %s
                """, (column,))
                
                if cursor.fetchone():
                    query = f"CREATE INDEX {index_name} ON locations USING GIN ({column})"
                    cursor.execute(query)
                    conn.commit()
                    logger.info(f"✅ Index GIN créé: {index_name} sur {column}")
                else:
                    logger.warning(f"⚠️  Colonne '{column}' n'existe pas, index GIN non créé")
                    
        except Exception as e:
            logger.error(f"❌ Erreur création index GIN {index_name}: {e}")
            conn.rollback()
    
    # Statistiques finales
    logger.info("\n" + "="*60)
    logger.info("📊 MIGRATION TERMINÉE")
    logger.info("="*60)
    logger.info(f"Colonnes ajoutées: {added_count}")
    logger.info(f"Colonnes existantes: {skipped_count}")
    logger.info("="*60)
    
    # Afficher le nombre de POIs à enrichir
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN latitude IS NULL OR latitude = 0 THEN 1 END) as sans_coords,
            COUNT(CASE WHEN fsq_id IS NULL THEN 1 END) as non_enrichis
        FROM locations 
        WHERE source_url LIKE '%tokyocheapo%'
    """)
    
    result = cursor.fetchone()
    if result:
        logger.info(f"\n📈 État des POIs Tokyo Cheapo:")
        logger.info(f"  Total: {result[0]}")
        logger.info(f"  Sans coordonnées: {result[1]}")
        logger.info(f"  Non enrichis Foursquare: {result[2]}")
    
    cursor.close()
    conn.close()


if __name__ == "__main__":
    migrate_database()