"""Market analysis module for French real estate.

This module provides:
- Market data for Île-de-France cities (rental and sale prices)
- City profiles with safety, transport, growth ratings
- Market comparison tools (is this property above/below market?)
- Rental market estimates based on location
- Live market price scraping from SeLoger
"""

from .market_analyzer import MarketAnalyzer, MarketComparison, MarketContext
from .market_data import (
    CityProfile,
    IDF_CITY_PROFILES,
    IDF_MARKET_DATA,
    MarketData,
    MarketDataProvider,
)
from .market_scraper import fetch_current_prices, LiveMarketPrice, SeLogerMarketScraper

__all__ = [
    # Market data (cached)
    "MarketData",
    "CityProfile",
    "MarketDataProvider",
    "IDF_MARKET_DATA",
    "IDF_CITY_PROFILES",
    # Market analyzer
    "MarketAnalyzer",
    "MarketComparison",
    "MarketContext",
    # Live market scraper
    "SeLogerMarketScraper",
    "LiveMarketPrice",
    "fetch_current_prices",
]
