"""SeLoger market price scraper.

This module scrapes real-time rental and sale price data from SeLoger.com
to get current market prices per m² for French cities.

Based on seloger_project/seloger_profitability.py logic.
"""

import re
import time
import random
from dataclasses import dataclass
from typing import Optional, Tuple, Dict
from collections import Counter

import requests


# French departments and regions mapping
DEPARTMENTS = {
    # Ile-de-France
    "75": {"name": "paris", "region": "ile-de-france"},
    "77": {"name": "seine-et-marne", "region": "ile-de-france"},
    "78": {"name": "yvelines", "region": "ile-de-france"},
    "91": {"name": "essonne", "region": "ile-de-france"},
    "92": {"name": "hauts-de-seine", "region": "ile-de-france"},
    "93": {"name": "seine-saint-denis", "region": "ile-de-france"},
    "94": {"name": "val-de-marne", "region": "ile-de-france"},
    "95": {"name": "val-d-oise", "region": "ile-de-france"},
    # Lyon
    "69": {"name": "rhone", "region": "auvergne-rhone-alpes"},
    # Marseille
    "13": {"name": "bouches-du-rhone", "region": "provence-alpes-cote-d-azur"},
    # Bordeaux
    "33": {"name": "gironde", "region": "nouvelle-aquitaine"},
    # Toulouse
    "31": {"name": "haute-garonne", "region": "occitanie"},
    # Nantes
    "44": {"name": "loire-atlantique", "region": "pays-de-la-loire"},
    # Nice
    "06": {"name": "alpes-maritimes", "region": "provence-alpes-cote-d-azur"},
    # Strasbourg
    "67": {"name": "bas-rhin", "region": "grand-est"},
    # Lille
    "59": {"name": "nord", "region": "hauts-de-france"},
    # Montpellier
    "34": {"name": "herault", "region": "occitanie"},
}

# Common cities with their INSEE codes
CITIES_INSEE = {
    # Paris arrondissements
    "paris-1er": "75101", "paris-2eme": "75102", "paris-3eme": "75103",
    "paris-4eme": "75104", "paris-5eme": "75105", "paris-6eme": "75106",
    "paris-7eme": "75107", "paris-8eme": "75108", "paris-9eme": "75109",
    "paris-10eme": "75110", "paris-11eme": "75111", "paris-12eme": "75112",
    "paris-13eme": "75113", "paris-14eme": "75114", "paris-15eme": "75115",
    "paris-16eme": "75116", "paris-17eme": "75117", "paris-18eme": "75118",
    "paris-19eme": "75119", "paris-20eme": "75120",
    
    # Hauts-de-Seine (92)
    "montrouge": "92049", "malakoff": "92046", "vanves": "92075",
    "issy-les-moulineaux": "92040", "boulogne-billancourt": "92012",
    "clamart": "92023", "meudon": "92048", "sevres": "92072",
    "saint-cloud": "92064", "rueil-malmaison": "92063", "suresnes": "92073",
    "puteaux": "92062", "neuilly-sur-seine": "92051", "levallois-perret": "92044",
    "clichy": "92024", "asnieres-sur-seine": "92004", "courbevoie": "92026",
    "colombes": "92025", "nanterre": "92050", "gennevilliers": "92036",
    "chatillon": "92020", "bagneux": "92007", "fontenay-aux-roses": "92032",
    "chatenay-malabry": "92019", "sceaux": "92071", "antony": "92002",
    "bourg-la-reine": "92014", "le-plessis-robinson": "92060",
    "la-garenne-colombes": "92035", "bois-colombes": "92009",
    "villeneuve-la-garenne": "92078", "chaville": "92022", "garches": "92033",
    
    # Seine-Saint-Denis (93)
    "montreuil": "93048", "saint-denis": "93066", "aubervilliers": "93001",
    "pantin": "93055", "le-pre-saint-gervais": "93061", "les-lilas": "93045",
    "bagnolet": "93006", "romainville": "93063", "noisy-le-sec": "93053",
    "bondy": "93010", "bobigny": "93008", "drancy": "93029",
    "le-bourget": "93013", "la-courneuve": "93027", "stains": "93072",
    "pierrefitte-sur-seine": "93059", "villetaneuse": "93079",
    "epinay-sur-seine": "93031", "saint-ouen": "93070",
    
    # Val-de-Marne (94)
    "vincennes": "94080", "saint-mande": "94067", "charenton-le-pont": "94018",
    "maisons-alfort": "94046", "alfortville": "94002", "ivry-sur-seine": "94041",
    "vitry-sur-seine": "94081", "villejuif": "94076", "cachan": "94016",
    "gentilly": "94037", "le-kremlin-bicetre": "94043", "nogent-sur-marne": "94052",
    "le-perreux-sur-marne": "94058", "fontenay-sous-bois": "94033",
    "joinville-le-pont": "94042", "champigny-sur-marne": "94017", "creteil": "94028",
    "arcueil": "94003", "saint-maurice": "94069",
    
    # Val-d'Oise (95)
    "argenteuil": "95018", "sarcelles": "95585", "cergy": "95127",
    "pontoise": "95500", "enghien-les-bains": "95210",
    "garges-les-gonesse": "95268", "bezons": "95063",
    
    # Essonne (91)
    "evry-courcouronnes": "91228", "massy": "91377", "palaiseau": "91477",
    "corbeil-essonnes": "91174", "grigny": "91286", "ris-orangis": "91521",
}


@dataclass
class LiveMarketPrice:
    """Live market price data from SeLoger."""
    
    location_name: str
    rental_price_m2: Optional[float] = None  # €/m²/month
    sale_price_m2: Optional[float] = None  # €/m²
    rental_url: Optional[str] = None
    sale_url: Optional[str] = None
    error: Optional[str] = None
    fetched_at: Optional[str] = None
    
    @property
    def gross_yield(self) -> Optional[float]:
        """Calculate gross yield from rental and sale prices."""
        if self.rental_price_m2 and self.sale_price_m2:
            return (self.rental_price_m2 * 12 / self.sale_price_m2) * 100
        return None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "location_name": self.location_name,
            "rental_price_m2": self.rental_price_m2,
            "sale_price_m2": self.sale_price_m2,
            "gross_yield": round(self.gross_yield, 2) if self.gross_yield else None,
            "rental_url": self.rental_url,
            "sale_url": self.sale_url,
            "error": self.error,
            "fetched_at": self.fetched_at,
        }


class SeLogerMarketScraper:
    """Scraper for SeLoger market price data.
    
    This class fetches real-time rental and sale price averages per m²
    from SeLoger.com's market data pages.
    
    URL Pattern:
        https://www.seloger.com/prix-de-l-immo/{type}/{region}/{department}/{city}/{code}.htm
        
    Where:
        - type: "vente" (sale) or "location" (rental)
        - region: e.g., "ile-de-france"
        - department: e.g., "hauts-de-seine"
        - city: city slug, e.g., "montrouge"
        - code: INSEE code with "0" inserted after department (92049 → 920049)
    """
    
    BASE_URL = "https://www.seloger.com/prix-de-l-immo"
    
    # Price extraction strategies (regex patterns)
    MAIN_PRICE_PATTERNS = [
        r'data-testid="mainPrice"[^>]*>(\d+)\s*€',
        r'data-testid="mainPrice"[^>]*>\s*(\d+)\s*',
        r'data-testid="mainPrice"[^>]*>.*?(\d+)\s*€\s*/\s*m²',
        r'"mainPrice"[^>]*>(\d[\d\s]*)\s*€',
    ]
    
    JSON_PRICE_PATTERNS = [
        r'"averagePrice"\s*:\s*(\d+\.?\d*)',
        r'"avg"\s*:\s*(\d+\.?\d*)',
        r'"average"\s*:\s*(\d+\.?\d*)',
        r'"prixMoyen"\s*:\s*(\d+\.?\d*)',
    ]
    
    MINMAX_PATTERN = r'"min"\s*:\s*(\d+\.?\d*)[^}]*"max"\s*:\s*(\d+\.?\d*)'
    
    GENERAL_PRICE_PATTERNS = [
        r'(\d{1,2})\s*€\s*/\s*m²',
        r'(\d[\d\s\u202f]*)\s*€\s*/\s*m²',
    ]
    
    def __init__(self, delay_range: Tuple[float, float] = (1.0, 3.0)):
        """Initialize scraper.
        
        Args:
            delay_range: Min and max delay between requests (to avoid rate limiting)
        """
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                     "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })
        self.delay_range = delay_range
        self._last_request_time = 0
    
    def _rate_limit(self):
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        min_delay = random.uniform(*self.delay_range)
        if elapsed < min_delay:
            time.sleep(min_delay - elapsed)
        self._last_request_time = time.time()
    
    @staticmethod
    def insee_to_seloger_code(insee_code: str) -> str:
        """Convert INSEE code to SeLoger URL code.
        
        Pattern: Insert "0" after the first 2 digits (department code)
        Example: 92049 → 920049
        """
        if len(insee_code) == 5:
            return insee_code[:2] + "0" + insee_code[2:]
        return insee_code
    
    @staticmethod
    def city_name_to_slug(city_name: str) -> str:
        """Convert city name to URL slug."""
        slug = city_name.lower().strip()
        slug = re.sub(r"['\s]+", "-", slug)
        replacements = {
            "é": "e", "è": "e", "ê": "e", "ë": "e",
            "à": "a", "â": "a", "ä": "a",
            "î": "i", "ï": "i",
            "ô": "o", "ö": "o",
            "ù": "u", "û": "u", "ü": "u",
            "ç": "c",
        }
        for old, new in replacements.items():
            slug = slug.replace(old, new)
        return slug
    
    def build_url(
        self,
        city_name: str,
        transaction_type: str = "vente",
        insee_code: Optional[str] = None,
    ) -> Optional[str]:
        """Build SeLoger market price URL.
        
        Args:
            city_name: City name (e.g., "Montrouge", "Paris 15eme")
            transaction_type: "vente" (sale) or "location" (rental)
            insee_code: INSEE code (looked up from city_name if not provided)
            
        Returns:
            Full SeLoger URL or None if city not found
        """
        # Get INSEE code
        if not insee_code:
            slug = self.city_name_to_slug(city_name)
            insee_code = CITIES_INSEE.get(slug)
            
            if not insee_code:
                # Try partial match
                for city_slug, code in CITIES_INSEE.items():
                    if slug in city_slug or city_slug in slug:
                        insee_code = code
                        city_name = city_slug
                        break
        
        if not insee_code:
            return None
        
        # Get department info
        dept_code = insee_code[:2]
        dept_info = DEPARTMENTS.get(dept_code)
        
        if not dept_info:
            return None
        
        # Build URL
        region = dept_info["region"]
        department = dept_info["name"]
        city_slug = self.city_name_to_slug(city_name)
        seloger_code = self.insee_to_seloger_code(insee_code)
        
        return f"{self.BASE_URL}/{transaction_type}/{region}/{department}/{city_slug}/{seloger_code}.htm"
    
    def _clean_price(self, price_str: str) -> float:
        """Clean price string and convert to float."""
        clean = price_str.replace(' ', '').replace('\u202f', '').replace('\xa0', '')
        return float(clean)
    
    def _extract_price(self, html: str, is_rental: bool) -> Tuple[Optional[float], str]:
        """Extract price per m² from HTML.
        
        Args:
            html: Page HTML content
            is_rental: Whether this is a rental page
            
        Returns:
            Tuple of (price, error_message)
        """
        # Define valid price ranges
        if is_rental:
            min_price, max_price = 10, 60  # €/m²/month
        else:
            min_price, max_price = 1000, 30000  # €/m²
        
        # Strategy 1: data-testid="mainPrice"
        for pattern in self.MAIN_PRICE_PATTERNS:
            matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
            for match in matches:
                try:
                    price = self._clean_price(match)
                    if min_price <= price <= max_price:
                        return price, ""
                except ValueError:
                    continue
        
        # Strategy 2: JSON embedded data
        for pattern in self.JSON_PRICE_PATTERNS:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                try:
                    price = float(match)
                    if min_price <= price <= max_price:
                        return price, ""
                except ValueError:
                    continue
        
        # Strategy 3: Min/max average
        minmax_matches = re.findall(self.MINMAX_PATTERN, html)
        for min_val, max_val in minmax_matches:
            try:
                avg_price = (float(min_val) + float(max_val)) / 2
                if min_price <= avg_price <= max_price:
                    return round(avg_price, 0), ""
            except ValueError:
                continue
        
        # Strategy 4: Most common valid price
        all_prices = []
        for pattern in self.GENERAL_PRICE_PATTERNS:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                try:
                    price = self._clean_price(match)
                    if min_price <= price <= max_price:
                        all_prices.append(price)
                except ValueError:
                    continue
        
        if all_prices:
            price_counts = Counter(all_prices)
            return price_counts.most_common(1)[0][0], ""
        
        return None, "No valid price found"
    
    def fetch_price(self, url: str) -> Tuple[Optional[float], str]:
        """Fetch price per m² from a SeLoger market page.
        
        Args:
            url: SeLoger market price URL
            
        Returns:
            Tuple of (price_per_m2, error_message)
        """
        self._rate_limit()
        
        try:
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                return None, f"HTTP {response.status_code}"
            
            html = response.text
            
            # Check for captcha
            if "captcha-delivery" in html or "Please enable JS" in html:
                return None, "Captcha blocked"
            
            is_rental = "/location/" in url
            return self._extract_price(html, is_rental)
            
        except requests.RequestException as e:
            return None, str(e)
    
    def fetch_market_prices(self, city_name: str) -> LiveMarketPrice:
        """Fetch both rental and sale prices for a city.
        
        Args:
            city_name: City name (e.g., "Montrouge")
            
        Returns:
            LiveMarketPrice with rental and sale data
        """
        from datetime import datetime
        
        # Build URLs
        sale_url = self.build_url(city_name, "vente")
        rental_url = self.build_url(city_name, "location")
        
        if not sale_url or not rental_url:
            return LiveMarketPrice(
                location_name=city_name,
                error=f"City '{city_name}' not found in database"
            )
        
        # Fetch sale price
        sale_price, sale_error = self.fetch_price(sale_url)
        
        # Fetch rental price
        rental_price, rental_error = self.fetch_price(rental_url)
        
        error = None
        if sale_error and rental_error:
            error = f"Sale: {sale_error}, Rental: {rental_error}"
        elif sale_error:
            error = f"Sale: {sale_error}"
        elif rental_error:
            error = f"Rental: {rental_error}"
        
        return LiveMarketPrice(
            location_name=city_name.title().replace("-", " "),
            rental_price_m2=rental_price,
            sale_price_m2=sale_price,
            rental_url=rental_url,
            sale_url=sale_url,
            error=error,
            fetched_at=datetime.now().isoformat(),
        )
    
    def fetch_multiple(
        self,
        cities: list[str],
        progress_callback=None,
    ) -> Dict[str, LiveMarketPrice]:
        """Fetch market prices for multiple cities.
        
        Args:
            cities: List of city names
            progress_callback: Optional callback(i, total, city, result)
            
        Returns:
            Dictionary of city_name -> LiveMarketPrice
        """
        results = {}
        total = len(cities)
        
        for i, city in enumerate(cities, 1):
            result = self.fetch_market_prices(city)
            results[city] = result
            
            if progress_callback:
                progress_callback(i, total, city, result)
        
        return results
    
    def get_available_cities(self) -> list[str]:
        """Get list of all available cities."""
        return list(CITIES_INSEE.keys())
    
    def get_idf_cities(self) -> list[str]:
        """Get list of Île-de-France cities only."""
        idf_depts = {"75", "77", "78", "91", "92", "93", "94", "95"}
        return [
            city for city, insee in CITIES_INSEE.items()
            if insee[:2] in idf_depts
        ]


def fetch_current_prices(city: str) -> Optional[LiveMarketPrice]:
    """Convenience function to fetch current market prices for a city.
    
    Args:
        city: City name (e.g., "Montrouge", "Paris 15eme")
        
    Returns:
        LiveMarketPrice or None if error
    """
    scraper = SeLogerMarketScraper()
    return scraper.fetch_market_prices(city)
