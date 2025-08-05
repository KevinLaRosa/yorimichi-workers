# 🔍 Tokyo Cheapo Restaurant URL Analysis

## 🧠 Deep Analysis Summary

### Problem Statement
The Tokyo Cheapo crawler is finding **0 restaurant URLs** despite having the pattern `/food-and-drink/` in the filter.

### Root Cause Analysis

After analyzing the code thoroughly, I've identified several potential issues:

1. **URL Pattern Mismatch**: The filter expects `/food-and-drink/` but Tokyo Cheapo might use different URL structures for restaurants (e.g., `/restaurant/`, `/food/`, `/dining/`, or direct slugs without category prefixes)

2. **Sitemap Structure**: The restaurant sitemaps might contain:
   - Direct restaurant URLs without category prefixes
   - Different URL patterns than expected
   - Media/image URLs that get filtered out
   - WordPress artifacts

3. **Filter Logic Issue**: The current filter at line 914:
   ```python
   if any(pattern in url for pattern in ['/place/', '/food-and-drink/', '/accommodation/']):
       filtered_urls.append(url)
   ```
   This is a whitelist approach that might be too restrictive.

### 📊 Diagnostic Approach

I've created a debug script (`debug_tokyo_cheapo_urls.py`) that will:
1. Download and analyze restaurant sitemaps
2. Extract actual URL patterns
3. Show pattern distribution
4. Test current filters against real data
5. Provide recommendations

### 🛠️ Proposed Solutions

#### Solution 1: Update URL Patterns (Most Likely Fix)
```python
# Update line 914 in main_crawler_tokyo_cheapo.py
# Add more restaurant-related patterns
if any(pattern in url for pattern in [
    '/place/', 
    '/food-and-drink/', 
    '/food/',
    '/restaurant/',
    '/restaurants/',
    '/dining/',
    '/eat/',
    '/accommodation/'
]):
    filtered_urls.append(url)
```

#### Solution 2: Blacklist Approach (More Inclusive)
```python
# Instead of whitelisting, exclude known non-POI patterns
if not any(pattern in url for pattern in [
    '/wp-content/uploads/',
    '/cdn.cheapoguides.com/wp-content/',
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg',
    '/feed/', '/comments/', '/trackback/',
    '/author/', '/tag/', '/category/',
    '/page/', '?', '#'
]):
    # Additional check: must be a path, not just domain
    if url.count('/') > 3:  # More than just https://domain.com/
        filtered_urls.append(url)
```

#### Solution 3: Content-Based Detection
```python
# For restaurant sitemaps specifically, be more permissive
if 'restaurant-sitemap' in sitemap_url:
    # For restaurant sitemaps, include all URLs except obvious media
    if not any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
        filtered_urls.append(url)
```

### 🔧 Immediate Fix

Based on the analysis, here's the most likely fix:

```python
# Replace lines 913-915 with:
# Different logic for different sitemap types
if 'restaurant-sitemap' in sitemap_url:
    # For restaurants, be more inclusive
    if not any(pattern in url for pattern in [
        '/wp-content/uploads/',
        '.jpg', '.jpeg', '.png', '.gif', '.webp',
        '/feed/', '/comments/', '/trackback/'
    ]):
        filtered_urls.append(url)
elif 'place-sitemap' in sitemap_url:
    # For places, use the place pattern
    if '/place/' in url:
        filtered_urls.append(url)
elif 'accommodation-sitemap' in sitemap_url:
    # For accommodation
    if '/accommodation/' in url:
        filtered_urls.append(url)
else:
    # Default behavior
    if any(pattern in url for pattern in ['/place/', '/food-and-drink/', '/accommodation/']):
        filtered_urls.append(url)
```

### 📋 Next Steps

1. **Run the debug script** to confirm actual URL patterns:
   ```bash
   python debug_tokyo_cheapo_urls.py
   ```

2. **Apply the fix** based on debug output

3. **Test with limit** to verify:
   ```bash
   python main_crawler_tokyo_cheapo.py --target restaurants --limit 5
   ```

### 🎯 Expected Outcome

After applying the fix, the crawler should:
- Find 200+ restaurant URLs (based on sitemap references)
- Successfully process restaurant pages
- Create restaurant POIs in the database

### ⚠️ Additional Considerations

1. **URL Structure Evolution**: Tokyo Cheapo might have changed their URL structure over time
2. **Mixed Content**: Some restaurant content might be under `/place/` instead of a dedicated restaurant path
3. **Sitemap Accuracy**: The sitemaps might include non-restaurant content that needs filtering during processing

### 🔍 Verification Commands

```bash
# Check current behavior
curl -s "https://tokyocheapo.com/restaurant-sitemap1.xml" | grep -o '<loc>[^<]*</loc>' | head -20

# Count restaurant URLs
curl -s "https://tokyocheapo.com/restaurant-sitemap1.xml" | grep -c '<loc>'
```