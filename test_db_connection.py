#!/usr/bin/env python3
"""
Script de test pour trouver la bonne configuration de connexion à la base de données
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2

# Charger les variables d'environnement
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
else:
    load_dotenv()

print("🔍 Test de connexion à la base de données Supabase")
print("=" * 60)

# Récupérer les variables
supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not supabase_url:
    print("❌ SUPABASE_URL non trouvée")
    sys.exit(1)

project_id = supabase_url.replace('https://', '').split('.')[0]
print(f"📋 Project ID: {project_id}")
print(f"🌍 URL: {supabase_url}")

# Essayer différentes configurations
configs = [
    {
        "name": "Pooler avec service role key",
        "host": "aws-0-ap-northeast-1.pooler.supabase.com",
        "port": 6543,
        "user": f"postgres.{project_id}",
        "password": service_role_key
    },
    {
        "name": "Direct avec service role key",
        "host": f"db.{project_id}.supabase.co",
        "port": 5432,
        "user": "postgres",
        "password": service_role_key
    }
]

# Si on a un mot de passe DB spécifique
db_password = os.getenv('SUPABASE_DB_PASSWORD')
if db_password:
    configs.insert(0, {
        "name": "Pooler avec DB password",
        "host": "aws-0-ap-northeast-1.pooler.supabase.com",
        "port": 6543,
        "user": f"postgres.{project_id}",
        "password": db_password
    })
    configs.insert(1, {
        "name": "Direct avec DB password",
        "host": f"db.{project_id}.supabase.co",
        "port": 5432,
        "user": "postgres",
        "password": db_password
    })

print(f"\n🧪 Test de {len(configs)} configurations...")
print("-" * 60)

for config in configs:
    print(f"\n📝 Test: {config['name']}")
    print(f"   Host: {config['host']}")
    print(f"   Port: {config['port']}")
    print(f"   User: {config['user']}")
    print(f"   Pass: {'*' * 10}...")
    
    try:
        conn = psycopg2.connect(
            host=config['host'],
            database='postgres',
            user=config['user'],
            password=config['password'],
            port=config['port'],
            sslmode='require',
            connect_timeout=5
        )
        
        # Tester une requête simple
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM locations")
        count = cursor.fetchone()[0]
        
        print(f"   ✅ SUCCÈS! Connexion réussie")
        print(f"   📊 {count} POIs dans la base")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎉 Configuration fonctionnelle trouvée!")
        print(f"   Utilisez cette configuration dans vos scripts")
        break
        
    except Exception as e:
        print(f"   ❌ Échec: {str(e)[:100]}")

print("\n" + "=" * 60)
print("\n💡 Note: Si aucune connexion ne fonctionne, vous devez:")
print("   1. Vérifier le mot de passe de la base de données dans Supabase Dashboard")
print("   2. Aller dans Settings > Database")
print("   3. Copier le 'Database password' (pas le service role key)")
print("   4. L'ajouter dans .env.local comme SUPABASE_DB_PASSWORD=...")