"""LeBonCoin.fr scraper implementation.

LeBonCoin uses DataDome anti-bot protection. The key to bypassing it:
1. Use a session to maintain cookies
2. Visit homepage first to get initial cookies
3. Use full browser-like headers including sec-ch-ua
"""

import json
import re
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from src.models.listing import (
    Address,
    AgentInfo,
    BuildingInfo,
    EnergyClass,
    EnergyRating,
    GESClass,
    PriceInfo,
    PropertyFeatures,
    PropertyType,
    TransportInfo,
)
from src.scraper.base import (
    BaseScraper,
    DescriptionParser,
    extract_dpe_class,
    extract_ges_class,
    extract_postal_code,
    FetchMode,
    ParseError,
    BlockedError,
)


class LeBonCoinScraper(BaseScraper):
    """Scraper for LeBonCoin.fr listings.
    
    Uses session-based requests with browser-like headers to bypass DataDome.
    """

    SOURCE_NAME = "leboncoin"
    
    # Browser-like headers that work with DataDome
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate', 
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }

    # URL pattern to extract listing ID
    ID_PATTERN = re.compile(r"/(?:ad/[^/]+/|oad/)(\d+)", re.IGNORECASE)

    def __init__(self, mode: FetchMode = FetchMode.REQUESTS, **kwargs):
        """Initialize LeBonCoin scraper.

        Args:
            mode: Fetch mode (default: REQUESTS with custom session handling)
            **kwargs: Additional arguments passed to BaseScraper
        """
        super().__init__(mode=mode, **kwargs)
        self._session: Optional[requests.Session] = None
        self._session_initialized = False
        
        # Import CacheManager from base
        from src.scraper.base import CacheManager
        self.cache_manager = CacheManager()

    def _get_session(self) -> requests.Session:
        """Get or create a session with cookies from homepage."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(self.HEADERS)
        
        # Initialize session by visiting homepage first
        if not self._session_initialized:
            try:
                self._session.get('https://www.leboncoin.fr/', timeout=10)
                self._session_initialized = True
            except Exception:
                pass  # Continue anyway
        
        return self._session

    def _fetch_html(self, url: str) -> str:
        """Fetch HTML using session-based requests."""
        session = self._get_session()
        
        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()
            
            if 'captcha' in response.text.lower() and '__NEXT_DATA__' not in response.text:
                raise BlockedError("Blocked by DataDome CAPTCHA")
            
            return response.text
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                raise BlockedError(f"Access forbidden (403) for {url}")
            raise

    def extract(self, url: str, use_cache: bool = True):
        """Extract listing data from URL.
        
        Overrides base method to use custom session-based fetching.
        """
        listing_id = self._extract_listing_id(url)
        cache_key = f"{self.SOURCE_NAME}_{listing_id}"
        
        # Try cache first
        if use_cache:
            cached = self.cache_manager.get(cache_key)
            if cached:
                soup = BeautifulSoup(cached, "html.parser")
                data = self._parse(soup, url)
                from src.models.listing import Listing
                return Listing(**data)
        
        # Fetch with our custom method
        html = self._fetch_html(url)
        
        # Cache it
        if use_cache:
            self.cache_manager.set(cache_key, html)
        
        soup = BeautifulSoup(html, "html.parser")
        data = self._parse(soup, url)
        
        from src.models.listing import Listing
        return Listing(**data)

    def _extract_listing_id(self, url: str) -> str:
        """Extract listing ID from LeBonCoin URL."""
        match = self.ID_PATTERN.search(url)
        if match:
            return match.group(1)
        # Fallback: use URL hash
        import hashlib

        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _extract_json_data(self, soup: BeautifulSoup) -> Optional[dict]:
        """Extract __NEXT_DATA__ JSON from LeBonCoin page."""
        # LeBonCoin uses Next.js, data is in __NEXT_DATA__
        script = soup.find("script", id="__NEXT_DATA__")
        if script and script.string:
            try:
                data = json.loads(script.string)
                return data
            except json.JSONDecodeError:
                pass
        return None

    def _get_ad_data(self, next_data: dict) -> Optional[dict]:
        """Extract ad data from __NEXT_DATA__ structure."""
        try:
            # Navigate to the ad data in Next.js structure
            props = next_data.get("props", {})
            page_props = props.get("pageProps", {})

            # Try different paths
            ad = page_props.get("ad")
            if ad:
                return ad

            # Alternative path
            initial_data = page_props.get("initialData", {})
            if "ad" in initial_data:
                return initial_data["ad"]

            return page_props
        except (KeyError, TypeError):
            return None

    def _extract_property_type(self, ad_data: dict) -> PropertyType:
        """Determine property type from ad data."""
        type_mapping = {
            "appartement": PropertyType.APARTMENT,
            "maison": PropertyType.HOUSE,
            "studio": PropertyType.STUDIO,
            "loft": PropertyType.LOFT,
            "duplex": PropertyType.DUPLEX,
            "terrain": PropertyType.OTHER,
            "parking": PropertyType.OTHER,
        }

        # Check category or attributes
        category = ad_data.get("category_name", "").lower()
        subject = ad_data.get("subject", "").lower()

        for key, prop_type in type_mapping.items():
            if key in category or key in subject:
                return prop_type

        # Check attributes
        attributes = ad_data.get("attributes", [])
        for attr in attributes:
            if attr.get("key") == "real_estate_type":
                value = attr.get("value", "").lower()
                for key, prop_type in type_mapping.items():
                    if key in value:
                        return prop_type

        return PropertyType.APARTMENT

    def _extract_attribute(self, attributes: list, key: str) -> Optional[Any]:
        """Extract a specific attribute from the attributes list."""
        for attr in attributes:
            if attr.get("key") == key:
                return attr.get("value")
        return None

    def _extract_attribute_values(self, attributes: list, key: str) -> list:
        """Extract values for a specific attribute key."""
        for attr in attributes:
            if attr.get("key") == key:
                return attr.get("values", [])
        return []

    def _parse(self, soup: BeautifulSoup, url: str) -> dict:
        """Parse LeBonCoin listing page and extract data."""
        # Extract JSON data from __NEXT_DATA__
        next_data = self._extract_json_data(soup)
        if not next_data:
            raise ParseError(f"Could not find __NEXT_DATA__ in page: {url}")

        ad_data = self._get_ad_data(next_data)
        if not ad_data:
            raise ParseError(f"Could not extract ad data from page: {url}")

        # Extract listing ID
        listing_id = str(ad_data.get("list_id", "")) or self._extract_listing_id(url)

        # Get attributes list
        attributes = ad_data.get("attributes", [])

        # Extract basic info
        price = ad_data.get("price", [0])
        if isinstance(price, list):
            price = price[0] if price else 0
        price = int(price) if price else 0

        # Surface
        surface = self._extract_attribute(attributes, "square")
        if surface:
            surface = float(str(surface).replace(",", ".").replace("m²", "").strip())
        else:
            surface = 0.0

        # Rooms and bedrooms
        rooms = self._extract_attribute(attributes, "rooms")
        rooms = int(rooms) if rooms else None

        bedrooms = self._extract_attribute(attributes, "bedrooms")
        bedrooms = int(bedrooms) if bedrooms else None

        # Address
        location = ad_data.get("location", {})
        city = location.get("city", "Unknown")
        postal_code = location.get("zipcode", "")
        department = location.get("department_name", "")
        region = location.get("region_name", "")

        # DPE and GES
        dpe_value = self._extract_attribute(attributes, "energy_rate")
        ges_value = self._extract_attribute(attributes, "ges")

        energy_class = (
            extract_dpe_class(str(dpe_value)) if dpe_value else EnergyClass.UNKNOWN
        )
        ges_class = extract_ges_class(str(ges_value)) if ges_value else GESClass.UNKNOWN

        # Floor
        floor = self._extract_attribute(attributes, "floor_number")
        floor = int(floor) if floor else None

        # Features
        elevator = self._extract_attribute(attributes, "elevator")
        has_elevator = elevator == "1" or elevator == "true" or elevator == True

        parking = self._extract_attribute(attributes, "parking")
        has_parking = parking is not None and parking != "0"

        # Charges
        charges = self._extract_attribute(attributes, "charges_included")
        monthly_charges = self._extract_attribute(attributes, "monthly_charges")
        if monthly_charges:
            annual_charges = int(float(monthly_charges) * 12)
        else:
            annual_charges = None

        # Property condition
        condition = self._extract_attribute(attributes, "real_estate_condition")

        # Furnished
        furnished = self._extract_attribute(attributes, "furnished")
        is_furnished = furnished == "1" or furnished == "true"

        # Build year
        year_built = self._extract_attribute(attributes, "construction_year")
        year_built = int(year_built) if year_built else None

        # Description
        description = ad_data.get("body", "")
        title = ad_data.get("subject", "")

        # Images
        images = ad_data.get("images", {})
        image_urls = images.get("urls_large", []) or images.get("urls", [])

        # Owner info
        owner = ad_data.get("owner", {})
        owner_name = owner.get("name", "")
        owner_type = owner.get("type", "")  # "pro" or "private"
        is_private = owner_type != "pro"

        # Build address data
        address_data = {
            "city": city,
            "postal_code": str(postal_code) if postal_code else "00000",
            "street": None,
            "neighborhood": None,
            "department": postal_code[:2] if len(str(postal_code)) >= 2 else None,
        }

        # Build price data
        price_data = {
            "price": max(price, 1),
            "charges": None,
            "annual_charges": annual_charges,
            "agency_fees_included": not is_private,
        }

        # Build features
        features_data = {
            "rooms": rooms,
            "bedrooms": bedrooms,
            "floor": floor,
            "has_elevator": has_elevator,
            "has_parking": has_parking,
            "is_furnished": is_furnished,
            "condition": condition,
            "year_built": year_built,
        }

        # Check for more features in description
        desc_lower = description.lower() if description else ""
        features_data["has_balcony"] = "balcon" in desc_lower
        features_data["has_terrace"] = "terrasse" in desc_lower
        features_data["has_garden"] = "jardin" in desc_lower
        features_data["has_cellar"] = "cave" in desc_lower
        features_data["has_pool"] = "piscine" in desc_lower

        # Build energy rating
        energy_data = {
            "energy_class": energy_class,
            "ges_class": ges_class,
            "energy_consumption": None,
            "ges_emission": None,
        }

        # Build agent info
        agent_data = {
            "name": owner_name,
            "agency": owner_name if not is_private else None,
            "phone": None,
            "is_private_seller": is_private,
        }

        # Property type
        property_type = self._extract_property_type(ad_data)

        # Validate required fields
        if surface <= 0:
            # Try to extract from title or description
            surface_match = re.search(r"(\d+)\s*m[²2]", f"{title} {description}")
            if surface_match:
                surface = float(surface_match.group(1))
            else:
                raise ParseError(f"Could not extract surface area from {url}")

        if price <= 0:
            raise ParseError(f"Could not extract price from {url}")

        # Build listing data
        return {
            "id": listing_id,
            "source": self.SOURCE_NAME,
            "url": url,
            "title": title,
            "description": description,
            "property_type": property_type,
            "surface_area": float(surface),
            "address": Address(**address_data),
            "price_info": PriceInfo(**price_data),
            "features": PropertyFeatures(**features_data),
            "building": BuildingInfo(),
            "transport": TransportInfo(),
            "energy_rating": EnergyRating(**energy_data),
            "agent": AgentInfo(**agent_data),
            "images": image_urls,
            "raw_data": {"ad_data": ad_data},
        }
