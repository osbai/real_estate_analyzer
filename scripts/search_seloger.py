#!/usr/bin/env python3
"""Search SeLoger and extract listing URLs from search results.

Usage:
    python scripts/search_seloger.py [URL] [OPTIONS]

Examples:
    # Search with default URL
    python scripts/search_seloger.py

    # Search with custom URL
    python scripts/search_seloger.py "https://www.seloger.com/classified-search?..."

    # Save to custom cache file
    python scripts/search_seloger.py --output my_search.json

    # Load cached results and display
    python scripts/search_seloger.py --load search_results.json
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup
from src.scraper.base import RequestsClient


# Default cache directory
CACHE_DIR = Path(__file__).parent.parent / ".cache" / "searches"


def extract_listing_urls(html: str) -> list[str]:
    """Extract listing URLs from SeLoger search results HTML."""
    soup = BeautifulSoup(html, "html.parser")
    listing_urls = set()

    # Pattern for SeLoger listing URLs
    for link in soup.find_all("a", href=True):
        href = link["href"]
        # Match /annonces/.../<id>.htm pattern
        if "/annonces/" in href and re.search(r"/\d+\.htm", href):
            if href.startswith("/"):
                href = "https://www.seloger.com" + href
            listing_urls.add(href)

    return sorted(listing_urls)


def extract_search_params(url: str) -> dict:
    """Extract search parameters from URL for metadata."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    # Flatten single-value lists
    return {k: v[0] if len(v) == 1 else v for k, v in params.items()}


def generate_cache_filename(url: str) -> str:
    """Generate a cache filename based on URL hash and timestamp."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"seloger_search_{timestamp}_{url_hash}.json"


def save_results(
    listing_urls: list[str],
    search_url: str,
    output_path: Optional[Path] = None,
) -> Path:
    """Save search results to a JSON cache file.

    Args:
        listing_urls: List of extracted listing URLs
        search_url: Original search URL
        output_path: Optional custom output path

    Returns:
        Path to the saved cache file
    """
    # Ensure cache directory exists
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Generate output path if not provided
    if output_path is None:
        output_path = CACHE_DIR / generate_cache_filename(search_url)
    elif not output_path.is_absolute():
        output_path = CACHE_DIR / output_path

    # Build cache data
    cache_data = {
        "metadata": {
            "source": "seloger",
            "search_url": search_url,
            "search_params": extract_search_params(search_url),
            "fetched_at": datetime.now().isoformat(),
            "total_listings": len(listing_urls),
        },
        "listings": listing_urls,
    }

    # Save to file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)

    return output_path


def load_results(cache_path: Path) -> dict:
    """Load search results from a cache file.

    Args:
        cache_path: Path to the cache file

    Returns:
        Cache data dictionary
    """
    if not cache_path.exists():
        # Try in cache directory
        cache_path = CACHE_DIR / cache_path

    with open(cache_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_cached_searches() -> list[Path]:
    """List all cached search result files."""
    if not CACHE_DIR.exists():
        return []
    return sorted(CACHE_DIR.glob("seloger_search_*.json"), reverse=True)


def print_results(listing_urls: list[str], limit: int = 10):
    """Print listing URLs to console."""
    print(f"\nFound {len(listing_urls)} listing URLs:")
    print()
    for i, u in enumerate(listing_urls[:limit], 1):
        print(f"{i:2}. {u}")
    if len(listing_urls) > limit:
        print(f"    ... and {len(listing_urls) - limit} more")


def main():
    parser = argparse.ArgumentParser(
        description="Search SeLoger and extract listing URLs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/search_seloger.py
  python scripts/search_seloger.py "https://www.seloger.com/classified-search?..."
  python scripts/search_seloger.py --output my_results.json
  python scripts/search_seloger.py --load seloger_search_20240101_120000_abc123.json
  python scripts/search_seloger.py --list
        """,
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=(
            "https://www.seloger.com/classified-search?"
            "availableFromMax=2026-05-01&"
            "distributionTypes=Buy&"
            "energyCertificate=A,B,C,D&"
            "estateTypes=House,Apartment&"
            "locations=AD04FR5&"
            "priceMax=250000&"
            "priceMin=150000"
        ),
        help="SeLoger search URL (default: sample Île-de-France search)",
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
        help="Number of URLs to display (default: 10, use 0 for all)",
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

    args = parser.parse_args()

    # List cached searches
    if args.list:
        cached = list_cached_searches()
        if not cached:
            print("No cached searches found.")
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
                    price_range = (
                        f"{params.get('priceMin', '?')}-{params.get('priceMax', '?')}€"
                    )
                    print(f"    → Price: {price_range}")
                print()
            except Exception:
                print(f"  {path.name} (error reading)")
        return

    # Load from cache
    if args.load:
        try:
            data = load_results(Path(args.load))
            listing_urls = data.get("listings", [])
            meta = data.get("metadata", {})

            if args.urls_only:
                for url in listing_urls:
                    print(url)
                return

            print(f"Loaded {len(listing_urls)} listings from cache")
            print(f"  Search URL: {meta.get('search_url', 'unknown')[:60]}...")
            print(f"  Fetched at: {meta.get('fetched_at', 'unknown')}")

            limit = args.limit if args.limit > 0 else len(listing_urls)
            print_results(listing_urls, limit)

            print(f"\n💡 To compare these listings, run:")
            print(f'   python scripts/compare_listings.py --from-cache "{args.load}"')
        except FileNotFoundError:
            print(f"Error: Cache file not found: {args.load}")
            print(f"Available caches: {CACHE_DIR}")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in cache file: {args.load}")
            sys.exit(1)
        return

    # Fetch new results
    url = args.url
    print("Fetching search results using RequestsClient...")
    print(f"URL: {url[:80]}...")
    print()

    client = RequestsClient()

    try:
        html = client.fetch(url)
        print(f"Fetched {len(html)} bytes")

        # Check if blocked
        if "captcha" in html.lower() or "enable JS" in html:
            print("\nBLOCKED: Page requires JavaScript/Captcha")
            print("SeLoger search results require a headless browser.")
            sys.exit(1)

        listing_urls = extract_listing_urls(html)

        if not listing_urls:
            print("\nNo listing URLs found in the page.")
            print("Page preview:")
            print(html[:1000])
            sys.exit(1)

        # Output URLs only mode
        if args.urls_only:
            for u in listing_urls:
                print(u)
            return

        # Display results
        limit = args.limit if args.limit > 0 else len(listing_urls)
        print_results(listing_urls, limit)

        # Save to cache
        if not args.no_cache:
            output_path = Path(args.output) if args.output else None
            cache_path = save_results(listing_urls, url, output_path)
            print(f"\n✅ Saved {len(listing_urls)} listings to: {cache_path}")
            print(f"\n💡 To load later, run:")
            print(f'   python scripts/search_seloger.py --load "{cache_path.name}"')
            print(f"\n💡 To compare all listings, run:")
            print(
                f'   python scripts/compare_listings.py --from-cache "{cache_path.name}"'
            )

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
