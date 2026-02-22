"""Base scraper infrastructure with caching and HTTP utilities."""

import hashlib
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from src.models.listing import EnergyClass, GESClass, Listing


# === Exception Classes ===


class ScraperError(Exception):
    """Base exception for scraper errors."""

    pass


class FetchError(ScraperError):
    """HTTP/network related errors."""

    pass


class ParseError(ScraperError):
    """HTML parsing failures."""

    pass


class ValidationError(ScraperError):
    """Data doesn't fit Listing model."""

    pass


class RateLimitError(FetchError):
    """Rate limited by the website."""

    pass


class BlockedError(FetchError):
    """Blocked by anti-bot measures."""

    pass


# === Rate Limiter ===


@dataclass
class RateLimiter:
    """Rate limiter with per-domain tracking and randomized delays.

    Implements human-like request patterns to avoid detection.
    """

    min_delay: float = 2.0  # Minimum seconds between requests
    max_delay: float = 5.0  # Maximum seconds between requests
    burst_protection_delay: float = 30.0  # Delay after multiple rapid requests
    burst_threshold: int = 5  # Number of requests before burst protection kicks in
    _last_request_time: dict = field(default_factory=dict)
    _request_counts: dict = field(default_factory=dict)
    _burst_window: float = 60.0  # Window in seconds to track burst

    def wait(self, domain: str) -> None:
        """Wait appropriate time before next request to domain."""
        current_time = time.time()

        # Initialize tracking for new domains
        if domain not in self._last_request_time:
            self._last_request_time[domain] = 0
            self._request_counts[domain] = []

        # Clean old request timestamps (outside burst window)
        self._request_counts[domain] = [
            t for t in self._request_counts[domain] if current_time - t < self._burst_window
        ]

        # Check if we're in burst territory
        if len(self._request_counts[domain]) >= self.burst_threshold:
            delay = self.burst_protection_delay + random.uniform(5, 15)
            time.sleep(delay)
            self._request_counts[domain] = []  # Reset after burst delay
        else:
            # Calculate time since last request
            elapsed = current_time - self._last_request_time[domain]

            # Add randomized delay to appear more human-like
            required_delay = random.uniform(self.min_delay, self.max_delay)

            if elapsed < required_delay:
                sleep_time = required_delay - elapsed
                # Add jitter (±20%)
                jitter = sleep_time * random.uniform(-0.2, 0.2)
                time.sleep(max(0, sleep_time + jitter))

        # Record this request
        self._last_request_time[domain] = time.time()
        self._request_counts[domain].append(time.time())

    def add_penalty(self, domain: str, seconds: float) -> None:
        """Add penalty delay for a domain (e.g., after receiving 429)."""
        time.sleep(seconds)
        self._last_request_time[domain] = time.time()


# === Cache Manager ===


class CacheManager:
    """Manages HTML caching with SHA256 hashing."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path(__file__).parent.parent / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_hash(self, url: str) -> str:
        """Generate SHA256 hash of URL."""
        return hashlib.sha256(url.encode()).hexdigest()

    def _get_cache_path(self, url: str) -> Path:
        """Get cache file path for URL."""
        return self.cache_dir / f"{self._get_hash(url)}.html"

    def get(self, url: str) -> Optional[str]:
        """Retrieve cached HTML for URL, or None if not cached."""
        cache_path = self._get_cache_path(url)
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8")
        return None

    def set(self, url: str, html: str) -> None:
        """Cache HTML content for URL."""
        cache_path = self._get_cache_path(url)
        cache_path.write_text(html, encoding="utf-8")

    def clear(self, url: Optional[str] = None) -> int:
        """Clear cache. If URL provided, clear only that entry. Returns count of cleared files."""
        if url:
            cache_path = self._get_cache_path(url)
            if cache_path.exists():
                cache_path.unlink()
                return 1
            return 0
        else:
            count = 0
            for cache_file in self.cache_dir.glob("*.html"):
                cache_file.unlink()
                count += 1
            return count


# === HTTP Client ===


class HTTPClient:
    """HTTP client with anti-bot protection measures.

    Features:
    - Rate limiting with randomized delays
    - User agent rotation
    - Session persistence (cookies)
    - Referer header simulation
    - Retry with exponential backoff
    - Proxy support (optional)
    """

    # Realistic browser headers
    DEFAULT_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "DNT": "1",
    }

    # Common referers to simulate coming from search engines
    REFERERS = [
        "https://www.google.fr/",
        "https://www.google.com/",
        "https://www.bing.com/",
        "https://duckduckgo.com/",
        "https://www.qwant.com/",
        None,  # Sometimes no referer (direct visit)
    ]

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0,
        rate_limiter: Optional[RateLimiter] = None,
        proxy: Optional[str] = None,
        respect_robots_txt: bool = True,
    ):
        """Initialize HTTP client with anti-blocking measures.

        Args:
            max_retries: Maximum retry attempts for failed requests
            base_delay: Base delay for exponential backoff
            rate_limiter: Custom rate limiter (uses default if None)
            proxy: Optional proxy URL (e.g., "http://proxy:8080")
            respect_robots_txt: Whether to check robots.txt (placeholder)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.rate_limiter = rate_limiter or RateLimiter()
        self.proxy = proxy
        self.respect_robots_txt = respect_robots_txt
        self._ua = UserAgent()
        self._sessions: dict[str, httpx.Client] = {}
        self._last_referer: Optional[str] = None

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        return urlparse(url).netloc

    def _get_session(self, domain: str) -> httpx.Client:
        """Get or create a persistent session for a domain.

        Maintains cookies across requests to the same domain.
        """
        if domain not in self._sessions:
            transport = None
            if self.proxy:
                transport = httpx.HTTPTransport(proxy=self.proxy)

            self._sessions[domain] = httpx.Client(
                timeout=30.0,
                follow_redirects=True,
                transport=transport,
            )
        return self._sessions[domain]

    def _get_headers(self, url: str) -> dict:
        """Get headers with rotated user agent and realistic referer."""
        headers = self.DEFAULT_HEADERS.copy()

        # Rotate user agent (keep same one for session-like behavior sometimes)
        if random.random() > 0.7:  # 30% chance to rotate
            headers["User-Agent"] = self._ua.random
        else:
            # Use a consistent "Chrome on Mac" user agent
            headers["User-Agent"] = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )

        # Set referer (sometimes from search, sometimes from same site)
        if self._last_referer and random.random() > 0.5:
            # 50% chance to use last visited page as referer (browsing behavior)
            headers["Referer"] = self._last_referer
        else:
            referer = random.choice(self.REFERERS)
            if referer:
                headers["Referer"] = referer

        # Add origin for same-site requests
        domain = self._get_domain(url)
        headers["Origin"] = f"https://{domain}"

        return headers

    def _check_for_blocking(self, response: httpx.Response) -> None:
        """Check if response indicates we've been blocked."""
        # Check for common blocking indicators
        content_lower = response.text.lower() if response.text else ""

        blocking_indicators = [
            "access denied",
            "blocked",
            "captcha",
            "robot",
            "unusual traffic",
            "rate limit",
            "too many requests",
            "please verify you are human",
            "cloudflare",
            "ddos protection",
        ]

        for indicator in blocking_indicators:
            if indicator in content_lower:
                raise BlockedError(
                    f"Blocked by anti-bot measures (detected: {indicator})"
                )

    def fetch(self, url: str, timeout: float = 30.0) -> str:
        """Fetch URL with anti-blocking measures.

        Features applied:
        1. Rate limiting with random delays
        2. Session persistence (cookies maintained)
        3. User agent rotation
        4. Referer simulation
        5. Retry with exponential backoff
        6. Block detection

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds

        Returns:
            HTML content as string

        Raises:
            FetchError: If unable to fetch after retries
            RateLimitError: If rate limited by website
            BlockedError: If blocked by anti-bot measures
        """
        domain = self._get_domain(url)
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                # Apply rate limiting before request
                self.rate_limiter.wait(domain)

                # Get persistent session
                session = self._get_session(domain)

                # Make request with realistic headers
                response = session.get(
                    url,
                    headers=self._get_headers(url),
                    timeout=timeout,
                )

                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    self.rate_limiter.add_penalty(domain, retry_after)
                    raise RateLimitError(f"Rate limited, retry after {retry_after}s")

                # Check for blocking
                if response.status_code == 403:
                    self._check_for_blocking(response)
                    raise BlockedError(f"Access forbidden (403) for {url}")

                response.raise_for_status()

                # Check response content for soft blocks
                self._check_for_blocking(response)

                # Update last referer for next request
                self._last_referer = url

                return response.text

            except (RateLimitError, BlockedError):
                raise

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (403, 429):
                    # Rate limited or blocked - wait much longer
                    delay = self.base_delay * (2**attempt) * 3 + random.uniform(5, 15)
                else:
                    delay = self.base_delay * (2**attempt)

            except httpx.RequestError as e:
                last_error = e
                delay = self.base_delay * (2**attempt)

            if attempt < self.max_retries - 1:
                # Add jitter to delay
                jitter = delay * random.uniform(-0.2, 0.3)
                time.sleep(delay + jitter)

        raise FetchError(
            f"Failed to fetch {url} after {self.max_retries} attempts: {last_error}"
        )

    def close(self) -> None:
        """Close all persistent sessions."""
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# === Utility Functions ===


def extract_price(text: str) -> int:
    """Extract price from French formatted text.

    Examples:
        "350 000 €" → 350000
        "1 250 000€" → 1250000
        "89.000 €" → 89000
    """
    if not text:
        return 0
    # Remove currency symbols, spaces, and non-breaking spaces
    cleaned = re.sub(r"[€\s\u00a0]", "", text)
    # Handle European decimal separator (periods for thousands)
    cleaned = cleaned.replace(".", "").replace(",", "")
    # Extract digits
    match = re.search(r"\d+", cleaned)
    if match:
        return int(match.group())
    return 0


def extract_surface(text: str) -> float:
    """Extract surface area from text.

    Examples:
        "65 m²" → 65.0
        "120,5m2" → 120.5
        "85.7 m²" → 85.7
    """
    if not text:
        return 0.0
    # Normalize the text
    cleaned = text.replace(",", ".").replace("\u00a0", " ")
    # Match number before m² or m2
    match = re.search(r"(\d+(?:\.\d+)?)\s*m[²2]", cleaned, re.IGNORECASE)
    if match:
        return float(match.group(1))
    # Try matching just a number
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if match:
        return float(match.group(1))
    return 0.0


def extract_rooms(text: str) -> Optional[int]:
    """Extract room count from text.

    Examples:
        "3 pièces" → 3
        "T4" → 4
        "F2" → 2
    """
    if not text:
        return None
    # Match "X pièces" pattern
    match = re.search(r"(\d+)\s*(?:pièces?|p\.?)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    # Match T or F notation (French apartment classification)
    match = re.search(r"[TF](\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def extract_bedrooms(text: str) -> Optional[int]:
    """Extract bedroom count from text.

    Examples:
        "2 chambres" → 2
        "1 chambre" → 1
    """
    if not text:
        return None
    match = re.search(r"(\d+)\s*chambres?", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def extract_postal_code(text: str) -> str:
    """Extract French postal code from text.

    Examples:
        "92120 Montrouge" → "92120"
        "Paris 75008" → "75008"
    """
    if not text:
        return ""
    match = re.search(r"\b(\d{5})\b", text)
    if match:
        return match.group(1)
    return ""


def extract_dpe_class(text_or_element) -> EnergyClass:
    """Parse DPE energy class from text or element.

    Examples:
        "A" → EnergyClass.A
        "dpe-E" → EnergyClass.E
        "Classe énergie : D" → EnergyClass.D
    """
    if hasattr(text_or_element, "get_text"):
        text = text_or_element.get_text()
    else:
        text = str(text_or_element)

    # Match single letter A-G
    match = re.search(r"\b([A-G])\b", text.upper())
    if match:
        letter = match.group(1)
        try:
            return EnergyClass(letter)
        except ValueError:
            pass
    return EnergyClass.UNKNOWN


def extract_ges_class(text_or_element) -> GESClass:
    """Parse GES emission class from text or element."""
    if hasattr(text_or_element, "get_text"):
        text = text_or_element.get_text()
    else:
        text = str(text_or_element)

    match = re.search(r"\b([A-G])\b", text.upper())
    if match:
        letter = match.group(1)
        try:
            return GESClass(letter)
        except ValueError:
            pass
    return GESClass.UNKNOWN


def extract_floor(text: str) -> Optional[int]:
    """Extract floor number from text.

    Examples:
        "3ème étage" → 3
        "RDC" → 0
        "1er étage" → 1
    """
    if not text:
        return None
    text_lower = text.lower()
    if (
        "rdc" in text_lower
        or "rez-de-chaussée" in text_lower
        or "rez de chaussée" in text_lower
    ):
        return 0
    match = re.search(r"(\d+)\s*(?:e|è|ème|er)?\s*(?:étage)?", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


# === Base Scraper ===


class BaseScraper(ABC):
    """Abstract base class for real estate scrapers."""

    # Override in subclasses
    SOURCE_NAME: str = "unknown"

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        http_client: Optional[HTTPClient] = None,
    ):
        self.cache = cache_manager or CacheManager()
        self.http = http_client or HTTPClient()

    def _fetch_html(self, url: str, use_cache: bool = True) -> str:
        """Fetch HTML with caching support."""
        if use_cache:
            cached = self.cache.get(url)
            if cached:
                return cached

        html = self.http.fetch(url)

        if use_cache:
            self.cache.set(url, html)

        return html

    def _get_soup(self, html: str) -> BeautifulSoup:
        """Parse HTML into BeautifulSoup object."""
        return BeautifulSoup(html, "lxml")

    @abstractmethod
    def _extract_listing_id(self, url: str) -> str:
        """Extract unique listing ID from URL."""
        pass

    @abstractmethod
    def _parse(self, soup: BeautifulSoup, url: str) -> dict:
        """Parse HTML and extract listing data as dictionary.

        Returns a dict compatible with Listing model constructor.
        """
        pass

    def extract(self, url: str, use_cache: bool = True) -> Listing:
        """Extract listing data from URL.

        Args:
            url: The listing URL to scrape
            use_cache: Whether to use cached HTML (default True)

        Returns:
            Listing object with extracted data

        Raises:
            FetchError: If unable to fetch the URL
            ParseError: If unable to parse the HTML
            ValidationError: If data doesn't fit the Listing model
        """
        try:
            html = self._fetch_html(url, use_cache=use_cache)
        except FetchError:
            raise
        except Exception as e:
            raise FetchError(f"Error fetching {url}: {e}") from e

        try:
            soup = self._get_soup(html)
            data = self._parse(soup, url)
        except ParseError:
            raise
        except Exception as e:
            raise ParseError(f"Error parsing {url}: {e}") from e

        try:
            return Listing(**data)
        except Exception as e:
            raise ValidationError(
                f"Error validating listing data from {url}: {e}"
            ) from e
