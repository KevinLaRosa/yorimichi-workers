#!/usr/bin/env python3
"""
Debug script to analyze Tokyo Cheapo restaurant URLs
"""

import requests
from bs4 import BeautifulSoup
import re
from collections import Counter

def analyze_sitemap(sitemap_url):
    """Analyze a sitemap and return URL patterns"""
    print(f"\n{'='*60}")
    print(f"Analyzing: {sitemap_url}")
    print(f"{'='*60}")
    
    try:
        # Download sitemap
        resp = requests.get(sitemap_url, timeout=30)
        soup = BeautifulSoup(resp.content, 'xml')
        
        # Extract all URLs
        urls = [loc.text for loc in soup.find_all('loc')]
        print(f"Total URLs found: {len(urls)}")
        
        if not urls:
            print("⚠️ No URLs found in sitemap!")
            return
        
        # Analyze URL patterns
        patterns = Counter()
        path_segments = Counter()
        
        print("\n📊 Sample URLs (first 10):")
        for i, url in enumerate(urls[:10]):
            print(f"  {i+1}. {url}")
            
            # Extract path patterns
            path = url.replace('https://tokyocheapo.com/', '')
            segments = path.split('/')
            
            if len(segments) > 0:
                patterns[segments[0]] += 1
                path_segments[f"/{segments[0]}/"] += 1
        
        print(f"\n📈 URL Pattern Analysis:")
        print(f"Most common first segments:")
        for pattern, count in patterns.most_common(10):
            print(f"  - /{pattern}/: {count} URLs")
        
        # Check for specific patterns
        print(f"\n🔍 Checking for expected patterns:")
        expected_patterns = ['/place/', '/food-and-drink/', '/food/', '/restaurant/', '/restaurants/', '/dining/']
        
        for pattern in expected_patterns:
            matching = [url for url in urls if pattern in url]
            print(f"  - '{pattern}': {len(matching)} matches")
            if matching and len(matching) <= 3:
                print(f"    Examples: {matching[:3]}")
        
        # Check what patterns actually exist
        print(f"\n🎯 Actual URL structures found:")
        unique_patterns = set()
        for url in urls:
            # Extract the pattern between domain and final slug
            match = re.search(r'tokyocheapo\.com/([^/]+/)', url)
            if match:
                unique_patterns.add(match.group(1))
        
        for pattern in sorted(unique_patterns):
            count = sum(1 for url in urls if f"/{pattern}" in url)
            print(f"  - /{pattern}: {count} URLs")
        
        # Filter analysis
        print(f"\n🚦 Current filter test:")
        current_filters = ['/place/', '/food-and-drink/', '/accommodation/']
        filtered_count = 0
        for url in urls:
            if any(pattern in url for pattern in current_filters):
                filtered_count += 1
        
        print(f"  Current filters would capture: {filtered_count}/{len(urls)} URLs")
        
        # Check for WordPress patterns to exclude
        print(f"\n🚫 WordPress/Media URLs to exclude:")
        wp_patterns = ['/wp-content/', '.jpg', '.jpeg', '.png', '.gif', '.webp', '/feed/', '/comments/']
        wp_count = 0
        for url in urls:
            if any(pattern in url.lower() for pattern in wp_patterns):
                wp_count += 1
        print(f"  WordPress/Media URLs: {wp_count}/{len(urls)}")
        
        return urls
        
    except Exception as e:
        print(f"❌ Error analyzing sitemap: {str(e)}")
        return None

def main():
    """Main analysis function"""
    print("🔍 Tokyo Cheapo Restaurant URL Debug Tool")
    print("="*60)
    
    # Restaurant sitemaps
    restaurant_sitemaps = [
        "https://tokyocheapo.com/restaurant-sitemap1.xml",
        "https://tokyocheapo.com/restaurant-sitemap2.xml"
    ]
    
    all_restaurant_urls = []
    
    for sitemap in restaurant_sitemaps:
        urls = analyze_sitemap(sitemap)
        if urls:
            all_restaurant_urls.extend(urls)
    
    print(f"\n📊 SUMMARY")
    print(f"{'='*60}")
    print(f"Total restaurant URLs: {len(all_restaurant_urls)}")
    
    # Final recommendation
    print(f"\n💡 RECOMMENDATIONS:")
    print("Based on the analysis above, update the filter pattern to match actual URL structures")
    
    # Test some real restaurant pages
    if all_restaurant_urls:
        print(f"\n🌐 Testing actual restaurant page structure:")
        test_url = next((url for url in all_restaurant_urls if 'wp-content' not in url and not url.endswith(('.jpg', '.png'))), None)
        if test_url:
            print(f"  Testing: {test_url}")
            try:
                resp = requests.get(test_url, timeout=10)
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Check page structure
                title = soup.find('h1')
                if title:
                    print(f"  Page title: {title.get_text(strip=True)}")
                
                # Check for restaurant indicators
                content = soup.get_text().lower()
                restaurant_indicators = ['menu', 'cuisine', 'restaurant', 'food', 'dining', 'chef', 'dishes']
                found_indicators = [ind for ind in restaurant_indicators if ind in content]
                print(f"  Restaurant indicators found: {found_indicators}")
                
            except Exception as e:
                print(f"  Error testing page: {str(e)}")

if __name__ == "__main__":
    main()