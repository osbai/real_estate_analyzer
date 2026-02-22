#!/usr/bin/env python3
"""Search LeBonCoin for real estate listings and extract URLs.

Usage:
    python scripts/search_leboncoin.py [URL] [OPTIONS]

Examples:
    # Search with URL from browser
    python scripts/search_leboncoin.py "https://www.leboncoin.fr/recherche?category=9&..."

    # Fetch ALL pages (pagination)
    python scripts/search_leboncoin.py --all-pages
    python scripts/search_leboncoin.py --max-pages 5

    # Save to custom cache file
    python scripts/search_leboncoin.py --output my_search.json

    # Load cached results and display
    python scripts/search_leboncoin.py --load leboncoin_search_xxx.json
"""

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import requests

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Default cache directory
CACHE_DIR = Path(__file__).parent.parent / ".cache" / "searches"

# Browser-like headers for LeBonCoin API
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.leboncoin.fr",
    "Referer": "https://www.leboncoin.fr/recherche",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

# LeBonCoin API endpoint
API_URL = "https://api.leboncoin.fr/finder/search"


def parse_search_url(url: str) -> dict:
    """Parse LeBonCoin search URL parameters into API filters.

    Example URL parameters:
        category=9                  -> Real estate for sale
        locations=r_12              -> Île-de-France region
        price=min-300000            -> Price range
        rooms=2-2                   -> 2 rooms
        square=38-max               -> Min 38m²
        bedrooms=1-1                -> 1 bedroom
        real_estate_type=2          -> Apartment
        immo_sell_type=old,new      -> Old and new
        floor_property=upper_floor  -> Upper floors
        energy_rate=a,b,c,d         -> DPE A-D
        global_condition=1,2,3      -> Condition
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    # Flatten single-value lists
    flat_params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}

    # Build API filters
    filters: dict[str, Any] = {
        "category": {"id": flat_params.get("category", "9")},
        "keywords": {},
    }

    # Location
    locations = flat_params.get("locations", "")
    if locations.startswith("r_"):
        # Region ID (e.g., r_12 for Île-de-France)
        region_id = locations[2:]
        filters["location"] = {"regions": [region_id]}
    elif locations.startswith("d_"):
        # Department ID (e.g., d_93 for Seine-Saint-Denis)
        dept_id = locations[2:]
        filters["location"] = {"departments": [dept_id]}
    elif "_" in locations and "__" in locations:
        # City format: CityName_PostalCode__lat_lng_xxx_radius
        # Example: Aubervilliers_93300__48.9136_2.38237_2133_5000
        parts = locations.split("_")
        city_name = parts[0]
        postal_code = parts[1] if len(parts) > 1 else ""
        
        # Extract department from postal code (first 2 digits)
        dept = postal_code[:2] if len(postal_code) >= 2 else ""
        
        # Extract coordinates if present (after double underscore)
        coord_parts = locations.split("__")
        if len(coord_parts) > 1:
            coords = coord_parts[1].split("_")
            if len(coords) >= 2:
                try:
                    lat = float(coords[0])
                    lng = float(coords[1])
                    radius = int(coords[3]) if len(coords) > 3 else 5000  # Default 5km
                    # Use area filter with coordinates
                    filters["location"] = {
                        "area": {
                            "lat": lat,
                            "lng": lng,
                            "radius": radius
                        }
                    }
                except (ValueError, IndexError):
                    # Fallback to department
                    if dept:
                        filters["location"] = {"departments": [dept]}
                    else:
                        filters["location"] = {"city_zipcodes": [{"city": city_name, "zipcode": postal_code}]}
            else:
                # Fallback to department
                if dept:
                    filters["location"] = {"departments": [dept]}
                else:
                    filters["location"] = {"city_zipcodes": [{"city": city_name, "zipcode": postal_code}]}
        else:
            # Fallback to department
            if dept:
                filters["location"] = {"departments": [dept]}
            else:
                filters["location"] = {"city_zipcodes": [{"city": city_name, "zipcode": postal_code}]}
    elif locations:
        # Simple location (zipcode or city name)
        filters["location"] = {"city_zipcodes": [{"zipcode": locations}]}

    # Price range
    price = flat_params.get("price", "")
    if price:
        price_filter = {}
        if "-" in price:
            parts = price.split("-")
            if parts[0] and parts[0] != "min":
                price_filter["min"] = int(parts[0])
            if len(parts) > 1 and parts[1] and parts[1] != "max":
                price_filter["max"] = int(parts[1])
        if price_filter:
            filters.setdefault("ranges", {})["price"] = price_filter

    # Rooms range
    rooms = flat_params.get("rooms", "")
    if rooms:
        rooms_filter = {}
        if "-" in rooms:
            parts = rooms.split("-")
            if parts[0] and parts[0].isdigit():
                rooms_filter["min"] = int(parts[0])
            if len(parts) > 1 and parts[1] and parts[1].isdigit():
                rooms_filter["max"] = int(parts[1])
        elif rooms.isdigit():
            rooms_filter["min"] = int(rooms)
            rooms_filter["max"] = int(rooms)
        if rooms_filter:
            filters.setdefault("ranges", {})["rooms"] = rooms_filter

    # Surface range
    square = flat_params.get("square", "")
    if square:
        square_filter = {}
        if "-" in square:
            parts = square.split("-")
            if parts[0] and parts[0].isdigit():
                square_filter["min"] = int(parts[0])
            if len(parts) > 1 and parts[1] and parts[1].isdigit():
                square_filter["max"] = int(parts[1])
        elif square.isdigit():
            square_filter["min"] = int(square)
        if square_filter:
            filters.setdefault("ranges", {})["square"] = square_filter

    # Bedrooms range
    bedrooms = flat_params.get("bedrooms", "")
    if bedrooms:
        bedrooms_filter = {}
        if "-" in bedrooms:
            parts = bedrooms.split("-")
            if parts[0] and parts[0].isdigit():
                bedrooms_filter["min"] = int(parts[0])
            if len(parts) > 1 and parts[1] and parts[1].isdigit():
                bedrooms_filter["max"] = int(parts[1])
        elif bedrooms.isdigit():
            bedrooms_filter["min"] = int(bedrooms)
            bedrooms_filter["max"] = int(bedrooms)
        if bedrooms_filter:
            filters.setdefault("ranges", {})["bedrooms"] = bedrooms_filter

    # Enums (multiple choice filters)
    enums: dict[str, list] = {}

    # Real estate type (1=house, 2=apartment, etc.)
    real_estate_type = flat_params.get("real_estate_type", "")
    if real_estate_type:
        enums["real_estate_type"] = real_estate_type.split(",")

    # Immo sell type (old, new, viager)
    immo_sell_type = flat_params.get("immo_sell_type", "")
    if immo_sell_type:
        enums["immo_sell_type"] = immo_sell_type.split(",")

    # Floor property
    floor_property = flat_params.get("floor_property", "")
    if floor_property:
        enums["floor_property"] = floor_property.split(",")

    # Energy rate (DPE)
    energy_rate = flat_params.get("energy_rate", "")
    if energy_rate:
        enums["energy_rate"] = energy_rate.split(",")

    # Global condition
    global_condition = flat_params.get("global_condition", "")
    if global_condition:
        enums["real_estate_condition"] = global_condition.split(",")

    if enums:
        filters["enums"] = enums

    return filters


def fetch_search_page(session: requests.Session, url: str) -> tuple[list[dict], int]:
    """Fetch search page HTML and extract listings.
    
    Uses the LeBonCoinScraper's session approach.

    Returns:
        Tuple of (ads_list, total_count)
    """
    # Import and use the working scraper's session approach
    from src.scraper.leboncoin import LeBonCoinScraper
    
    scraper = LeBonCoinScraper()
    html = scraper._fetch_html(url)
    
    # Extract __NEXT_DATA__ JSON
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', html)
    if not match:
        raise ValueError("Could not find __NEXT_DATA__ in search page")

    data = json.loads(match.group(1))

    # Navigate to ads in the search data structure
    props = data.get("props", {}).get("pageProps", {})
    search_data = props.get("searchData", {})
    ads = search_data.get("ads", [])
    total = search_data.get("total", len(ads))

    return ads, total


def fetch_page(
    session: requests.Session,
    filters: dict,
    offset: int = 0,
    limit: int = 35,
) -> tuple[list[dict], int]:
    """Fetch a page of search results from LeBonCoin API.

    Returns:
        Tuple of (ads_list, total_count)
    """
    payload = {
        "limit": limit,
        "limit_alu": 3,
        "offset": offset,
        "filters": filters,
        "sort_by": "time",
        "sort_order": "desc",
    }

    response = session.post(API_URL, json=payload, headers=HEADERS, timeout=15)
    response.raise_for_status()

    data = response.json()
    ads = data.get("ads", [])
    total = data.get("total", 0)

    return ads, total


def ads_to_urls(ads: list[dict]) -> list[str]:
    """Convert ad objects to listing URLs."""
    urls = []
    for ad in ads:
        list_id = ad.get("list_id")
        url = ad.get("url", "")
        if list_id and url:
            # url already starts with /ad/... so just prepend domain
            if url.startswith("/"):
                full_url = f"https://www.leboncoin.fr{url}"
            else:
                full_url = url
            urls.append(full_url)
        elif list_id:
            # Fallback URL construction
            urls.append(f"https://www.leboncoin.fr/ad/ventes_immobilieres/{list_id}")
    return urls


def fetch_all_pages(
    session: requests.Session,
    filters: dict,
    max_pages: Optional[int] = None,
    delay: float = 1.0,
) -> tuple[list[dict], int]:
    """Fetch all pages of search results.

    Args:
        session: Requests session
        filters: API filters
        max_pages: Maximum number of pages to fetch (None for all)
        delay: Delay between requests in seconds

    Returns:
        Tuple of (all_ads, pages_fetched)
    """
    all_ads = []
    offset = 0
    limit = 35
    page = 1
    pages_fetched = 0
    total_count = None

    while True:
        print(f"  Page {page}: ", end="", flush=True)

        try:
            ads, total = fetch_page(session, filters, offset=offset, limit=limit)

            if page == 1:
                total_count = total
                print(f"({total} total) ", end="")

            if not ads:
                print("No more listings")
                break

            all_ads.extend(ads)
            pages_fetched += 1

            print(f"✓ {len(ads)} listings (total: {len(all_ads)})")

            # Check if we've fetched all
            if len(all_ads) >= total:
                print(f"  → Collected all {total} listings")
                break

            # Check max pages limit
            if max_pages and page >= max_pages:
                print(f"  → Reached max pages limit ({max_pages})")
                break

            page += 1
            offset += limit

            # Rate limiting delay
            time.sleep(delay)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"⚠️  Blocked (403 Forbidden) - DataDome rate limit")
                print("    Try again in a few minutes or use a VPN")
            else:
                print(f"⚠️  HTTP Error: {e}")
            break
        except Exception as e:
            print(f"⚠️  Error: {e}")
            break

    return all_ads, pages_fetched


def extract_search_params(url: str) -> dict:
    """Extract search parameters from URL for metadata."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return {k: v[0] if len(v) == 1 else v for k, v in params.items()}


def generate_cache_filename(url: str) -> str:
    """Generate a cache filename based on URL hash and timestamp."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"leboncoin_search_{timestamp}_{url_hash}.json"


def save_results(
    ads: list[dict],
    search_url: str,
    output_path: Optional[Path] = None,
) -> Path:
    """Save search results to a JSON cache file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = CACHE_DIR / generate_cache_filename(search_url)
    elif not output_path.is_absolute():
        output_path = CACHE_DIR / output_path

    # Extract URLs from ads
    listing_urls = ads_to_urls(ads)

    # Build cache data with both raw ads and URLs
    cache_data = {
        "metadata": {
            "source": "leboncoin",
            "search_url": search_url,
            "search_params": extract_search_params(search_url),
            "fetched_at": datetime.now().isoformat(),
            "total_listings": len(listing_urls),
        },
        "listings": listing_urls,
        "raw_ads": ads,  # Keep raw data for richer analysis
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)

    return output_path


def load_results(cache_path: Path) -> dict:
    """Load search results from a cache file."""
    if not cache_path.exists():
        cache_path = CACHE_DIR / cache_path

    with open(cache_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_cached_searches() -> list[Path]:
    """List all cached search result files."""
    if not CACHE_DIR.exists():
        return []
    return sorted(CACHE_DIR.glob("leboncoin_search_*.json"), reverse=True)


def print_results(ads: list[dict], limit: int = 10):
    """Print listing summaries to console."""
    print(f"\nFound {len(ads)} listings:")
    print()

    for i, ad in enumerate(ads[:limit], 1):
        list_id = ad.get("list_id", "?")
        subject = ad.get("subject", "N/A")
        price = ad.get("price", [0])
        if isinstance(price, list):
            price = price[0] if price else 0
        location = ad.get("location", {})
        city = location.get("city", "?")
        zipcode = location.get("zipcode", "")

        # Get attributes
        attrs = {a["key"]: a.get("value") for a in ad.get("attributes", [])}
        surface = attrs.get("square", "?")
        rooms = attrs.get("rooms", "?")
        dpe = attrs.get("energy_rate", "?")

        url_path = ad.get("url", "")
        if url_path.startswith("/"):
            url = f"https://www.leboncoin.fr{url_path}"
        else:
            url = url_path

        print(f"{i:2}. {subject}")
        print(f"    💰 {price:,}€ | 📐 {surface}m² | 🚪 {rooms}p | DPE: {dpe}")
        print(f"    📍 {city} ({zipcode})")
        print(f"    🔗 {url}")
        print()

    if len(ads) > limit:
        print(f"    ... and {len(ads) - limit} more")


def main():
    parser = argparse.ArgumentParser(
        description="Search LeBonCoin and extract listing URLs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/search_leboncoin.py "https://www.leboncoin.fr/recherche?category=9&..."
  python scripts/search_leboncoin.py --all-pages
  python scripts/search_leboncoin.py --output my_results.json
  python scripts/search_leboncoin.py --load leboncoin_search_xxx.json
  python scripts/search_leboncoin.py --list
        """,
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=(
            "https://www.leboncoin.fr/recherche?"
            "category=9&"
            "locations=r_12&"
            "price=min-300000&"
            "rooms=2-2&"
            "square=38-max&"
            "bedrooms=1-1&"
            "real_estate_type=2&"
            "immo_sell_type=old,new&"
            "floor_property=upper_floor&"
            "energy_rate=a,b,c,d&"
            "global_condition=1,2,3"
        ),
        help="LeBonCoin search URL",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output filename for cache (default: auto-generated)",
    )
    parser.add_argument(
        "-l",
        "--load",
        type=str,
        help="Load and display results from a cache file instead of fetching",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all cached search results",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=10,
        help="Number of listings to display (default: 10, use 0 for all)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Don't save results to cache file",
    )
    parser.add_argument(
        "--urls-only",
        action="store_true",
        help="Output only URLs (one per line), useful for piping",
    )
    parser.add_argument(
        "--all-pages",
        "-a",
        action="store_true",
        help="Fetch ALL pages of results (with pagination)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum number of pages to fetch (implies --all-pages)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between page requests in seconds (default: 1.0)",
    )

    args = parser.parse_args()

    # List cached searches
    if args.list:
        cached = list_cached_searches()
        if not cached:
            print("No cached LeBonCoin searches found.")
            return

        print(f"Found {len(cached)} cached searches in {CACHE_DIR}:\n")
        for path in cached[:20]:
            try:
                data = load_results(path)
                meta = data.get("metadata", {})
                print(f"  {path.name}")
                print(f"    → {meta.get('total_listings', '?')} listings")
                print(f"    → {meta.get('fetched_at', 'unknown date')}")
                params = meta.get("search_params", {})
                if params:
                    price = params.get("price", "?")
                    rooms = params.get("rooms", "?")
                    print(f"    → Price: {price}, Rooms: {rooms}")
                print()
            except Exception:
                print(f"  {path.name} (error reading)")
        return

    # Load from cache
    if args.load:
        try:
            data = load_results(Path(args.load))
            listing_urls = data.get("listings", [])
            raw_ads = data.get("raw_ads", [])
            meta = data.get("metadata", {})

            if args.urls_only:
                for url in listing_urls:
                    print(url)
                return

            print(f"Loaded {len(listing_urls)} listings from cache")
            print(f"  Search URL: {meta.get('search_url', 'unknown')[:60]}...")
            print(f"  Fetched at: {meta.get('fetched_at', 'unknown')}")

            limit = args.limit if args.limit > 0 else len(raw_ads)
            if raw_ads:
                print_results(raw_ads, limit)
            else:
                # Fallback to just URLs
                print(f"\nFound {len(listing_urls)} listing URLs:")
                for i, url in enumerate(listing_urls[:limit], 1):
                    print(f"{i:2}. {url}")

            print(f"\n💡 To compare these listings, run:")
            print(f'   python scripts/compare_listings.py --from-cache "{args.load}"')
        except FileNotFoundError:
            print(f"Error: Cache file not found: {args.load}")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in cache file: {args.load}")
            sys.exit(1)
        return

    # Fetch new results
    url = args.url
    use_pagination = args.all_pages or args.max_pages is not None

    print("Fetching LeBonCoin search results via API...")
    print(f"URL: {url[:80]}...")
    if use_pagination:
        max_pages_str = str(args.max_pages) if args.max_pages else "unlimited"
        print(f"Pagination: enabled (max pages: {max_pages_str}, delay: {args.delay}s)")
    print()

    # Create session with proper initialization (like the working scraper)
    session = requests.Session()

    # Use same headers as working scraper for session init
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        }
    )

    # Visit homepage first to get cookies (required by DataDome)
    print("Initializing session (visiting homepage)...")
    try:
        session.get("https://www.leboncoin.fr/", timeout=10)
    except Exception as e:
        print(f"Warning: Could not initialize session: {e}")

    # Parse search URL to API filters
    filters = parse_search_url(url)
    print(f"Parsed filters: {json.dumps(filters, indent=2)[:200]}...")
    print()

    try:
        if use_pagination:
            # For pagination, first try HTML scraping, then fall back to API
            print("Fetching first page (HTML)...")
            try:
                ads, total = fetch_search_page(session, url)
                print(f"✓ Found {len(ads)} listings on page 1 (total: {total})")

                # For additional pages, we need to modify the URL with page param
                if total > len(ads) and (not args.max_pages or args.max_pages > 1):
                    all_ads = list(ads)
                    page = 2

                    while len(all_ads) < total:
                        if args.max_pages and page > args.max_pages:
                            print(f"  → Reached max pages limit ({args.max_pages})")
                            break

                        # Add page parameter to URL
                        page_url = f"{url}&page={page}"
                        print(f"  Page {page}: ", end="", flush=True)

                        time.sleep(args.delay)
                        page_ads, _ = fetch_search_page(session, page_url)

                        if not page_ads:
                            print("No more listings")
                            break

                        all_ads.extend(page_ads)
                        print(f"✓ {len(page_ads)} listings (total: {len(all_ads)})")
                        page += 1

                    ads = all_ads

                print(f"\n✓ Found {len(ads)} total listings")
            except Exception as e:
                print(f"HTML scraping failed ({e}), trying API...")
                ads, pages_fetched = fetch_all_pages(
                    session,
                    filters,
                    max_pages=args.max_pages,
                    delay=args.delay,
                )
                print(f"\n✓ Fetched {pages_fetched} pages, found {len(ads)} listings")
        else:
            # Single page fetch via HTML (like the working scraper)
            print("Fetching search page (HTML)...")
            ads, total = fetch_search_page(session, url)
            print(f"✓ Found {len(ads)} listings (total available: {total})")

        if not ads:
            print("\nNo listings found.")
            sys.exit(1)

        # Output URLs only mode
        if args.urls_only:
            for url in ads_to_urls(ads):
                print(url)
            return

        # Display results
        limit = args.limit if args.limit > 0 else len(ads)
        print_results(ads, limit)

        # Save to cache
        if not args.no_cache:
            output_path = Path(args.output) if args.output else None
            cache_path = save_results(ads, url, output_path)
            print(f"\n✅ Saved {len(ads)} listings to: {cache_path}")
            print(f"\n💡 To load later, run:")
            print(f'   python scripts/search_leboncoin.py --load "{cache_path.name}"')
            print(f"\n💡 To compare all listings, run:")
            print(
                f'   python scripts/compare_listings.py --from-cache "{cache_path.name}"'
            )

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
