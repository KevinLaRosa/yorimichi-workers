#!/usr/bin/env python3
"""
Direct debug of Tokyo Cheapo restaurant URLs
"""

import requests
from bs4 import BeautifulSoup

def analyze_restaurant_urls():
    """Analyze restaurant sitemap URLs directly"""
    
    restaurant_sitemaps = [
        "https://tokyocheapo.com/restaurant-sitemap1.xml",
        "https://tokyocheapo.com/restaurant-sitemap2.xml"
    ]
    
    for sitemap_url in restaurant_sitemaps:
        print(f"\n{'='*60}")
        print(f"Analyzing: {sitemap_url}")
        print(f"{'='*60}")
        
        try:
            resp = requests.get(sitemap_url, timeout=30)
            soup = BeautifulSoup(resp.content, 'xml')
            urls = [loc.text for loc in soup.find_all('loc')]
            
            print(f"Total URLs in sitemap: {len(urls)}")
            
            # Show first 20 URLs to understand the pattern
            print(f"\n🔍 First 20 URLs:")
            for i, url in enumerate(urls[:20]):
                print(f"{i+1:3d}. {url}")
            
            # Analyze URL patterns
            print(f"\n📊 URL Pattern Analysis:")
            
            # Check for common patterns
            patterns_to_check = [
                '/wp-content/uploads/',
                '/cdn.cheapoguides.com/wp-content/',
                '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg',
                '/feed/', '/comments/', '/trackback/',
                '/author/', '/tag/', '/page/',
                '/food-and-drink/',
                '/food/',
                '/restaurant/',
                '/place/'
            ]
            
            for pattern in patterns_to_check:
                count = sum(1 for url in urls if pattern in url.lower())
                if count > 0:
                    print(f"  - '{pattern}': {count} URLs ({count/len(urls)*100:.1f}%)")
            
            # Check what remains after exclusions
            exclusion_patterns = [
                '/wp-content/uploads/',
                '/cdn.cheapoguides.com/wp-content/',
                '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg',
                '/feed/', '/comments/', '/trackback/',
                '/author/', '/tag/', '/page/'
            ]
            
            filtered_urls = []
            excluded_urls = []
            
            for url in urls:
                if any(pattern in url.lower() for pattern in exclusion_patterns):
                    excluded_urls.append(url)
                else:
                    filtered_urls.append(url)
            
            print(f"\n🚦 Filtering Results:")
            print(f"  - Excluded: {len(excluded_urls)} URLs")
            print(f"  - Remaining: {len(filtered_urls)} URLs")
            
            if len(filtered_urls) > 0:
                print(f"\n✅ Sample of VALID restaurant URLs (first 10):")
                for i, url in enumerate(filtered_urls[:10]):
                    print(f"  {i+1}. {url}")
            else:
                print(f"\n❌ NO VALID URLs found after filtering!")
                print(f"\n🔍 Sample of EXCLUDED URLs (first 10):")
                for i, url in enumerate(excluded_urls[:10]):
                    # Find which pattern excluded it
                    excluded_by = [p for p in exclusion_patterns if p in url.lower()]
                    print(f"  {i+1}. {url}")
                    print(f"      Excluded by: {excluded_by}")
            
            # Check URL structure
            if len(urls) > 0:
                print(f"\n🏗️ URL Structure Analysis:")
                sample_url = urls[0]
                parts = sample_url.replace('https://tokyocheapo.com/', '').split('/')
                print(f"  Sample URL: {sample_url}")
                print(f"  Path segments: {parts}")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("🔍 Tokyo Cheapo Restaurant URL Debug Tool")
    print("="*60)
    analyze_restaurant_urls()