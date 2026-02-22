#!/usr/bin/env python3
"""Test script for SeLoger and PAP scrapers.

Usage:
    # Fetch and parse a URL (caches HTML for future runs)
    python scripts/test_scraper.py https://www.seloger.com/annonces/...

    # Parse from cached HTML only (no network request)
    python scripts/test_scraper.py https://www.seloger.com/annonces/... --cached-only

    # Clear cache and refetch
    python scripts/test_scraper.py https://www.seloger.com/annonces/... --refresh

    # Use headless browser (Playwright) for JS-heavy pages
    python scripts/test_scraper.py https://www.seloger.com/annonces/... --headless

    # Test with a local HTML file
    python scripts/test_scraper.py --file path/to/listing.html --source seloger

    # Show verbose parsing details
    python scripts/test_scraper.py https://www.pap.fr/annonces/... -v
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraper import get_scraper, CacheManager, FetchMode
from src.scraper.seloger import SeLogerScraper
from src.scraper.pap import PAPScraper


def test_from_url(
    url: str,
    cached_only: bool = False,
    refresh: bool = False,
    verbose: bool = False,
    mode: str = "simple",
):
    """Test scraping from a URL."""
    mode_display = {
        "requests": "REQUESTS (simple requests library)",
        "simple": "SIMPLE (httpx with anti-bot)",
        "headless": "HEADLESS (Playwright browser)",
    }
    
    print(f"\n{'='*60}")
    print(f"Testing URL: {url}")
    print(f"Mode: {mode_display.get(mode, mode)}")
    print(f"{'='*60}\n")

    cache = CacheManager()
    
    # Handle refresh
    if refresh:
        cleared = cache.clear(url)
        print(f"Cleared {cleared} cached file(s)")
    
    # Check cache status
    cached_html = cache.get(url)
    if cached_html:
        print(f"✓ Found cached HTML ({len(cached_html):,} bytes)")
    elif cached_only:
        print("✗ No cached HTML found. Run without --cached-only first.")
        return None
    else:
        print("→ No cache found, will fetch from network...")
    
    # Get appropriate scraper
    fetch_mode = {
        "requests": FetchMode.REQUESTS,
        "simple": FetchMode.SIMPLE,
        "headless": FetchMode.HEADLESS,
    }.get(mode, FetchMode.SIMPLE)
    
    try:
        scraper = get_scraper(url, mode=fetch_mode)
        print(f"✓ Using scraper: {scraper.__class__.__name__}")
    except ValueError as e:
        print(f"✗ Error: {e}")
        return None
    
    # Extract listing
    try:
        listing = scraper.extract(url, use_cache=not refresh)
        print("✓ Successfully extracted listing!")
    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return None
    finally:
        # Clean up resources
        scraper.close()
    
    # Display results
    print_listing(listing, verbose)
    return listing


def test_from_file(filepath: str, source: str, verbose: bool = False):
    """Test parsing from a local HTML file."""
    print(f"\n{'='*60}")
    print(f"Testing file: {filepath}")
    print(f"{'='*60}\n")
    
    path = Path(filepath)
    if not path.exists():
        print(f"✗ File not found: {filepath}")
        return None
    
    html = path.read_text(encoding="utf-8")
    print(f"✓ Loaded HTML ({len(html):,} bytes)")
    
    # Get scraper
    if source == "seloger":
        scraper = SeLogerScraper()
    elif source == "pap":
        scraper = PAPScraper()
    else:
        print(f"✗ Unknown source: {source}. Use 'seloger' or 'pap'")
        return None
    
    print(f"✓ Using scraper: {scraper.__class__.__name__}")
    
    # Parse
    try:
        soup = scraper._get_soup(html)
        fake_url = f"https://www.{source}.com/test/12345"
        data = scraper._parse(soup, fake_url)
        from src.models.listing import Listing
        listing = Listing(**data)
        print(f"✓ Successfully parsed listing!")
    except Exception as e:
        print(f"✗ Parsing failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return None
    
    print_listing(listing, verbose)
    return listing


def print_listing(listing, verbose: bool = False):
    """Print listing details."""
    print(f"\n{'-'*40}")
    print("LISTING SUMMARY")
    print(f"{'-'*40}")
    print(f"  {listing.summary()}")
    
    print(f"\n{'-'*40}")
    print("DETAILS")
    print(f"{'-'*40}")
    print(f"  ID:          {listing.id}")
    print(f"  Source:      {listing.source}")
    print(f"  Title:       {listing.title or '(none)'}")
    print(f"  Type:        {listing.property_type.value}")
    print(f"  Surface:     {listing.surface_area} m²")
    print(f"  Price:       {listing.price_info.price:,} €")
    print(f"  Price/m²:    {listing.price_per_sqm:,.0f} €/m²")
    
    print(f"\n  Address:")
    print(f"    City:      {listing.address.city}")
    print(f"    Postal:    {listing.address.postal_code}")
    if listing.address.neighborhood:
        print(f"    Area:      {listing.address.neighborhood}")
    
    print(f"\n  Features:")
    if listing.features.rooms:
        print(f"    Rooms:     {listing.features.rooms}")
    if listing.features.bedrooms:
        print(f"    Bedrooms:  {listing.features.bedrooms}")
    if listing.features.bathrooms:
        print(f"    Bathrooms: {listing.features.bathrooms}")
    if listing.features.floor is not None:
        print(f"    Floor:     {listing.features.floor}")
    
    amenities = []
    if listing.features.has_elevator:
        amenities.append("elevator")
    if listing.features.has_balcony:
        amenities.append("balcony")
    if listing.features.has_terrace:
        amenities.append("terrace")
    if listing.features.has_parking:
        amenities.append("parking")
    if listing.features.has_garden:
        amenities.append("garden")
    if listing.features.has_cellar:
        amenities.append("cellar")
    if amenities:
        print(f"    Amenities: {', '.join(amenities)}")
    
    print(f"\n  Energy:")
    print(f"    DPE:       {listing.energy_rating.energy_class.value}")
    print(f"    GES:       {listing.energy_rating.ges_class.value}")
    
    print(f"\n  Agent:")
    print(f"    Private:   {listing.agent.is_private_seller}")
    if listing.agent.agency:
        print(f"    Agency:    {listing.agent.agency}")
    
    if verbose and listing.description:
        print(f"\n{'-'*40}")
        print("DESCRIPTION")
        print(f"{'-'*40}")
        # Truncate long descriptions
        desc = listing.description[:500]
        if len(listing.description) > 500:
            desc += "..."
        print(f"  {desc}")
    
    if verbose:
        print(f"\n{'-'*40}")
        print("RAW JSON")
        print(f"{'-'*40}")
        print(listing.model_dump_json(indent=2, exclude={"raw_data"}))


def main():
    parser = argparse.ArgumentParser(
        description="Test SeLoger and PAP scrapers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "url",
        nargs="?",
        help="URL to scrape (SeLoger or PAP)"
    )
    parser.add_argument(
        "--file", "-f",
        help="Path to local HTML file to parse"
    )
    parser.add_argument(
        "--source", "-s",
        choices=["seloger", "pap"],
        default="seloger",
        help="Source website (for --file mode)"
    )
    parser.add_argument(
        "--cached-only", "-c",
        action="store_true",
        help="Only use cached HTML, don't fetch"
    )
    parser.add_argument(
        "--refresh", "-r",
        action="store_true",
        help="Clear cache and refetch"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including description and JSON"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Use headless browser (Playwright) for JS-rendered pages"
    )
    
    args = parser.parse_args()
    
    if args.file:
        test_from_file(args.file, args.source, args.verbose)
    elif args.url:
        test_from_url(
            args.url,
            args.cached_only,
            args.refresh,
            args.verbose,
            args.headless,
        )
    else:
        parser.print_help()
        print("\n\nExample URLs to try:")
        print("  SeLoger: https://www.seloger.com/annonces/achat/appartement/paris-11eme-75/...")
        print("  PAP:     https://www.pap.fr/annonces/appartement-paris-11e-r...")


if __name__ == "__main__":
    main()
