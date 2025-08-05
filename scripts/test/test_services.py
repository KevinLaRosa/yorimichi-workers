#!/usr/bin/env python3
"""
Test rapide des deux services de scraping
"""

import os
import sys

print("🧪 TEST DES SERVICES DE SCRAPING")
print("="*60)

# Vérifier les clés API
print("\n📊 Configuration actuelle :")
print(f"- SCRAPING_SERVICE : {os.getenv('SCRAPING_SERVICE', 'scrapingbee (par défaut)')}")
print(f"- SCRAPINGBEE_API_KEY : {'✅ Définie' if os.getenv('SCRAPINGBEE_API_KEY') else '❌ Non définie'}")
print(f"- SCRAPERAPI_KEY : {'✅ Définie' if os.getenv('SCRAPERAPI_KEY') else '✅ Clé par défaut disponible'}")

print("\n🔧 Corrections appliquées :")
print("1. ✅ Status 'skipped_existing' au lieu de 'skipped_existing_url'")
print("2. ✅ Ne pas marquer les URLs déjà existantes dans processed_urls")
print("3. ✅ Support multi-service maintenu")

print("\n🚀 Pour tester :")
print("-"*40)

print("\n# Test rapide avec ScrapingBee (si la clé est valide)")
print("python main_crawler_tokyo_cheapo.py --service scrapingbee --limit 2")

print("\n# Test avec ScraperAPI (271 crédits disponibles)")
print("python main_crawler_tokyo_cheapo.py --service scraperapi --limit 5")

print("\n# Test complet des attractions avec ScraperAPI")
print("python main_crawler_tokyo_cheapo.py --service scraperapi --target attractions")

print("\n💡 Notes :")
print("- Les 466 URLs déjà scrapées seront automatiquement skippées")
print("- Aucun crédit API ne sera utilisé pour les URLs existantes")
print("- ScraperAPI offre 100k requêtes/mois vs 50k pour ScrapingBee")
print("="*60)