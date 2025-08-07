#!/usr/bin/env python3
"""
Script pour forcer la suppression des doublons en utilisant une requête SQL directe
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Charger les variables d'environnement
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

def main():
    # Récupérer l'URL de la base de données
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        # Construire l'URL depuis les composants Supabase
        supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
        supabase_password = os.getenv('SUPABASE_DB_PASSWORD')
        
        if not supabase_url:
            print("❌ SUPABASE_URL manquante")
            print("\nPour utiliser ce script, ajoutez dans .env.local:")
            print("DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres")
            print("\nOu récupérez l'URL depuis:")
            print("Supabase Dashboard > Settings > Database > Connection String > URI")
            sys.exit(1)
        
        # Extraire le project-ref de l'URL
        # Format: https://[project-ref].supabase.co
        project_ref = supabase_url.split('//')[1].split('.')[0]
        
        if not supabase_password:
            print("❌ SUPABASE_DB_PASSWORD manquante")
            print("Récupérez le mot de passe depuis Supabase Dashboard > Settings > Database")
            sys.exit(1)
            
        # Construire l'URL de connexion (pooler pour éviter les problèmes de connexion)
        database_url = f"postgresql://postgres.{project_ref}:{supabase_password}@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"
    
    print("\n" + "="*60)
    print("🔥 SUPPRESSION FORCÉE DES DOUBLONS")
    print("="*60)
    
    try:
        # Connexion directe à PostgreSQL
        print("\n📡 Connexion à la base de données...")
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Compter les doublons
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM locations 
            WHERE enrichment_status = 'duplicate'
        """)
        result = cur.fetchone()
        total = result['count']
        
        if total == 0:
            print("✅ Aucun doublon à supprimer!")
            return
        
        print(f"📊 {total} doublons trouvés")
        
        # Afficher quelques exemples
        cur.execute("""
            SELECT name 
            FROM locations 
            WHERE enrichment_status = 'duplicate'
            LIMIT 10
        """)
        examples = cur.fetchall()
        
        print("\nExemples de doublons à supprimer:")
        for ex in examples:
            print(f"  - {ex['name']}")
        
        if total > 10:
            print(f"  ... et {total - 10} autres")
        
        # Confirmer
        confirm = input(f"\n⚠️ Voulez-vous supprimer ces {total} doublons? (yes/no): ")
        
        if confirm.lower() != 'yes':
            print("Annulé")
            return
        
        # Supprimer tous les doublons
        print("\n🗑️ Suppression en cours...")
        cur.execute("""
            DELETE FROM locations 
            WHERE enrichment_status = 'duplicate'
            RETURNING name
        """)
        
        deleted = cur.fetchall()
        conn.commit()
        
        print(f"\n✅ {len(deleted)} doublons supprimés avec succès!")
        
        # Afficher les noms supprimés
        if len(deleted) <= 20:
            print("\nPOIs supprimés:")
            for d in deleted:
                print(f"  ✓ {d['name']}")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
    
    print("="*60)


if __name__ == "__main__":
    main()