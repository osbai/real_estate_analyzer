"""Scraper module - auto-detect and extract listings from French real estate sites."""

import re
from typing import TYPE_CHECKING

from src.scraper.base import (
    BaseScraper,
    BlockedError,
    CacheManager,
    FetchError,
    HTTPClient,
    ParseError,
    RateLimiter,
    RateLimitError,
    ScraperError,
    ValidationError,
    extract_bedrooms,
    extract_dpe_class,
    extract_floor,
    extract_ges_class,
    extract_postal_code,
    extract_price,
    extract_rooms,
    extract_surface,
)

if TYPE_CHECKING:
    from src.scraper.pap import PAPScraper
    from src.scraper.seloger import SeLogerScraper


# URL patterns for site detection
URL_PATTERNS = {
    "seloger": re.compile(r"(?:www\.)?seloger\.com", re.IGNORECASE),
    "pap": re.compile(r"(?:www\.)?pap\.fr", re.IGNORECASE),
}


def get_scraper(url: str) -> BaseScraper:
    """Auto-detect site from URL and return appropriate scraper.

    Args:
        url: The listing URL to scrape

    Returns:
        Appropriate scraper instance for the URL

    Raises:
        ValueError: If the URL doesn't match any supported site

    Examples:
        >>> scraper = get_scraper("https://www.seloger.com/annonces/...")
        >>> isinstance(scraper, SeLogerScraper)
        True
    """
    for site_name, pattern in URL_PATTERNS.items():
        if pattern.search(url):
            if site_name == "seloger":
                from src.scraper.seloger import SeLogerScraper

                return SeLogerScraper()
            elif site_name == "pap":
                from src.scraper.pap import PAPScraper

                return PAPScraper()

    supported = ", ".join(URL_PATTERNS.keys())
    raise ValueError(f"Unsupported URL: {url}. Supported sites: {supported}")


__all__ = [
    # Factory
    "get_scraper",
    # Base classes
    "BaseScraper",
    "CacheManager",
    "HTTPClient",
    "RateLimiter",
    # Exceptions
    "ScraperError",
    "FetchError",
    "ParseError",
    "ValidationError",
    "RateLimitError",
    "BlockedError",
    # Utility functions
    "extract_price",
    "extract_surface",
    "extract_rooms",
    "extract_bedrooms",
    "extract_postal_code",
    "extract_dpe_class",
    "extract_ges_class",
    "extract_floor",
]
