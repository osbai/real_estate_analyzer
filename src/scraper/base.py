"""Base scraper infrastructure with caching and HTTP utilities."""

import hashlib
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import cloudscraper
import httpx
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from src.models.listing import EnergyClass, GESClass, Listing


class FetchMode(str, Enum):
    """Mode for fetching web pages."""

    REQUESTS = "requests"  # Use plain requests library (for SeLoger)
    CLOUDSCRAPER = "cloudscraper"  # Use cloudscraper (for PAP - bypasses Cloudflare)
    SIMPLE = "simple"  # Use httpx (async-capable, no JS)
    HEADLESS = "headless"  # Use Playwright (slower, renders JS)


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
            t
            for t in self._request_counts[domain]
            if current_time - t < self._burst_window
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


# === Simple Requests Client ===


class RequestsClient:
    """Simple HTTP client using plain requests library.

    Used for sites like SeLoger that work with basic requests.
    """

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    def __init__(self, timeout: float = 30.0):
        """Initialize plain requests client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        self._visited_sites: set = set()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        return urlparse(url).netloc

    def _warm_up_session(self, url: str) -> None:
        """Visit the homepage first to get cookies."""
        domain = self._get_domain(url)
        if domain in self._visited_sites:
            return

        parsed = urlparse(url)
        homepage = f"{parsed.scheme}://{parsed.netloc}/"

        try:
            self.session.get(homepage, timeout=self.timeout)
            self._visited_sites.add(domain)
            time.sleep(random.uniform(0.3, 0.8))
        except requests.exceptions.RequestException:
            pass

    def fetch(self, url: str, timeout: Optional[float] = None) -> str:
        """Fetch URL using plain requests.

        Args:
            url: URL to fetch
            timeout: Request timeout (uses default if not provided)

        Returns:
            HTML content as string

        Raises:
            FetchError: If unable to fetch the URL
        """
        try:
            self._warm_up_session(url)

            response = self.session.get(url, timeout=timeout or self.timeout)
            response.raise_for_status()
            return response.text

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                raise BlockedError(f"Access forbidden (403) for {url}") from e
            elif e.response.status_code == 429:
                raise RateLimitError(f"Rate limited (429) for {url}") from e
            raise FetchError(f"HTTP error fetching {url}: {e}") from e

        except requests.exceptions.RequestException as e:
            raise FetchError(f"Request error fetching {url}: {e}") from e

    def close(self) -> None:
        """Close the session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# === Cloudscraper Client ===


class CloudscraperClient:
    """HTTP client using cloudscraper to bypass anti-bot measures.

    Used for sites like PAP that have Cloudflare protection.
    Handles JavaScript challenges and TLS fingerprinting.
    """

    def __init__(self, timeout: float = 30.0):
        """Initialize cloudscraper client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "darwin",
                "mobile": False,
            },
            delay=1,
        )
        self._visited_sites: set = set()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        return urlparse(url).netloc

    def _warm_up_session(self, url: str) -> None:
        """Visit the homepage first to get cookies."""
        domain = self._get_domain(url)
        if domain in self._visited_sites:
            return

        parsed = urlparse(url)
        homepage = f"{parsed.scheme}://{parsed.netloc}/"

        try:
            self.session.get(homepage, timeout=self.timeout)
            self._visited_sites.add(domain)
            time.sleep(random.uniform(0.5, 1.5))
        except requests.exceptions.RequestException:
            pass

    def fetch(self, url: str, timeout: Optional[float] = None) -> str:
        """Fetch URL using cloudscraper to bypass anti-bot measures.

        Args:
            url: URL to fetch
            timeout: Request timeout (uses default if not provided)

        Returns:
            HTML content as string

        Raises:
            FetchError: If unable to fetch the URL
        """
        try:
            self._warm_up_session(url)

            response = self.session.get(url, timeout=timeout or self.timeout)
            response.raise_for_status()
            return response.text

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                raise BlockedError(f"Access forbidden (403) for {url}") from e
            elif e.response.status_code == 429:
                raise RateLimitError(f"Rate limited (429) for {url}") from e
            raise FetchError(f"HTTP error fetching {url}: {e}") from e

        except cloudscraper.exceptions.CloudflareChallengeError as e:
            raise BlockedError(f"Cloudflare challenge failed for {url}: {e}") from e

        except requests.exceptions.RequestException as e:
            raise FetchError(f"Request error fetching {url}: {e}") from e

    def close(self) -> None:
        """Close the session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# === Headless Browser Client ===


class HeadlessBrowserClient:
    """Headless browser client using Playwright for JavaScript-rendered pages.

    Use this when sites require JavaScript to render content (e.g., React/Vue apps).
    Falls back to HTTPClient behavior patterns for anti-bot measures.
    """

    def __init__(
        self,
        headless: bool = True,
        rate_limiter: Optional[RateLimiter] = None,
        browser_type: str = "chromium",  # chromium, firefox, webkit
    ):
        """Initialize headless browser client.

        Args:
            headless: Run browser in headless mode (default True)
            rate_limiter: Custom rate limiter (uses default if None)
            browser_type: Browser engine to use (chromium, firefox, webkit)

        Requires playwright to be installed:
            pip install playwright
            playwright install chromium
        """
        self.headless = headless
        self.rate_limiter = rate_limiter or RateLimiter()
        self.browser_type = browser_type
        self._playwright = None
        self._browser = None
        self._context = None

    def _ensure_browser(self):
        """Lazily initialize the browser."""
        if self._browser is not None:
            return

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError(
                "Playwright is required for headless browser mode. "
                "Install it with: pip install playwright && playwright install chromium"
            )

        self._playwright = sync_playwright().start()

        # Select browser type
        if self.browser_type == "firefox":
            browser_launcher = self._playwright.firefox
        elif self.browser_type == "webkit":
            browser_launcher = self._playwright.webkit
        else:
            browser_launcher = self._playwright.chromium

        # Launch with realistic settings
        self._browser = browser_launcher.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        # Create context with realistic browser fingerprint
        self._context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            timezone_id="Europe/Paris",
            geolocation={"latitude": 48.8566, "longitude": 2.3522},  # Paris
            permissions=["geolocation"],
            java_script_enabled=True,
            extra_http_headers={
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )

        # Add stealth scripts to avoid detection
        self._context.add_init_script(
            """
            // Overwrite navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Overwrite chrome automation flags
            window.chrome = {
                runtime: {}
            };

            // Overwrite permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """
        )

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        return urlparse(url).netloc

    def fetch(
        self,
        url: str,
        timeout: float = 30.0,
        wait_for_selector: Optional[str] = None,
        wait_for_load_state: str = "networkidle",
    ) -> str:
        """Fetch URL using headless browser.

        Args:
            url: URL to fetch
            timeout: Page load timeout in seconds
            wait_for_selector: CSS selector to wait for before returning
            wait_for_load_state: Load state to wait for:
                - "load": Wait for load event
                - "domcontentloaded": Wait for DOMContentLoaded
                - "networkidle": Wait until no network activity (default)

        Returns:
            Rendered HTML content as string

        Raises:
            FetchError: If unable to fetch the URL
            BlockedError: If blocked by anti-bot measures
        """
        domain = self._get_domain(url)

        # Apply rate limiting
        self.rate_limiter.wait(domain)

        # Ensure browser is initialized
        self._ensure_browser()

        try:
            # Create new page
            page = self._context.new_page()

            try:
                # Navigate with timeout
                page.goto(
                    url, timeout=int(timeout * 1000), wait_until="domcontentloaded"
                )

                # Wait for specific load state
                page.wait_for_load_state(
                    wait_for_load_state, timeout=int(timeout * 1000)
                )

                # Optionally wait for specific element
                if wait_for_selector:
                    page.wait_for_selector(
                        wait_for_selector, timeout=int(timeout * 1000)
                    )

                # Add random delay to simulate human behavior
                time.sleep(random.uniform(0.5, 2.0))

                # Scroll down a bit to trigger lazy loading
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
                time.sleep(random.uniform(0.3, 1.0))

                # Get rendered HTML
                html = page.content()

                # Check for blocking indicators
                content_lower = html.lower()
                blocking_indicators = [
                    "captcha",
                    "robot",
                    "blocked",
                    "access denied",
                    "cloudflare",
                ]
                for indicator in blocking_indicators:
                    if indicator in content_lower:
                        raise BlockedError(
                            f"Blocked by anti-bot measures (detected: {indicator})"
                        )

                return html

            finally:
                page.close()

        except BlockedError:
            raise
        except Exception as e:
            raise FetchError(f"Headless browser failed to fetch {url}: {e}") from e

    def close(self) -> None:
        """Close browser and cleanup resources."""
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

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


# === Description Parser ===


class DescriptionParser:
    """Parse French real estate descriptions to extract structured data."""

    # Building era patterns
    ERA_PATTERNS = {
        r"haussmann": "Haussmannien",
        r"années?\s*(\d{2})(?:s)?": lambda m: f"Années {m.group(1)}",
        r"ann[ée]es?\s*(19\d{2}|20\d{2})": lambda m: f"Années {m.group(1)[2:]}",
        r"immeuble\s+(?:des\s+)?années?\s*(\d{2,4})": lambda m: f"Années {m.group(1)[-2:]}",
        r"(19\d{2}|20\d{2})": None,  # Just extract year
        r"art\s*d[ée]co": "Art Déco",
        r"moderne": "Modern",
        r"récent": "Recent",
        r"neuf": "New",
        r"ancien": "Period",
    }

    # Condition patterns
    CONDITION_PATTERNS = {
        r"aucuns?\s+travaux\s+[àa]\s+pr[ée]voir": "No work needed",
        r"travaux\s+[àa]\s+pr[ée]voir": "Work needed",
        r"enti[èe]rement\s+[àa]\s+r[ée]nover": "Full renovation needed",
        r"[àa]\s+r[ée]nover": "To renovate",
        r"[àa]\s+rafra[iî]chir": "To refresh",
        r"refait\s+[àa]\s+neuf|enti[èe]rement\s+r[ée]nov[ée]": "Fully renovated",
        r"r[ée]nov[ée]|r[ée]fection": "Renovated",
        r"bon\s+[ée]tat|bien\s+entretenu": "Good condition",
        r"parfait\s+[ée]tat|excellent\s+[ée]tat": "Excellent condition",
        r"[ée]tat\s+neuf": "Like new",
    }

    # Orientation patterns
    ORIENTATION_PATTERNS = {
        r"plein\s+sud": "South",
        r"sud[\s\-]?ouest": "South-West",
        r"sud[\s\-]?est": "South-East",
        r"plein\s+nord": "North",
        r"nord[\s\-]?ouest": "North-West",
        r"nord[\s\-]?est": "North-East",
        r"plein\s+est": "East",
        r"plein\s+ouest": "West",
    }

    # Exposure patterns
    EXPOSURE_PATTERNS = {
        r"triple\s+exposition": "Triple",
        r"double\s+exposition": "Double",
        r"traversant": "Traversant",
        r"mono[\s\-]?orient[ée]": "Single",
    }

    # View patterns
    VIEW_PATTERNS = {
        r"vue\s+(?:sur\s+)?(?:le\s+)?jardin": "Garden",
        r"vue\s+(?:sur\s+)?(?:la\s+)?cour": "Courtyard",
        r"vue\s+(?:sur\s+)?(?:la\s+)?rue": "Street",
        r"vue\s+d[ée]gag[ée]e": "Open view",
        r"vue\s+(?:sur\s+)?(?:les?\s+)?toits?": "Rooftops",
        r"vue\s+(?:sur\s+)?(?:la\s+)?tour\s+eiffel": "Eiffel Tower",
        r"vue\s+(?:sur\s+)?(?:le\s+)?parc": "Park",
        r"sans\s+vis[\s\-]?[àa][\s\-]?vis": "No vis-à-vis",
    }

    @classmethod
    def parse(cls, description: str) -> dict:
        """Parse description and return extracted data.

        Returns a dict with keys:
        - features: PropertyFeatures fields
        - building: BuildingInfo fields
        - transport: TransportInfo fields
        - price_info: PriceInfo fields (annual_charges)
        - agent: AgentInfo fields (agency name)
        - address: Address fields (street)
        """
        if not description:
            return {}

        text = description.lower()
        result = {
            "features": {},
            "building": {},
            "transport": {},
            "price_info": {},
            "agent": {},
            "address": {},
        }

        # === Property Features ===

        # Building era / year
        for pattern, value in cls.ERA_PATTERNS.items():
            match = re.search(pattern, text)
            if match:
                if callable(value):
                    result["features"]["building_era"] = value(match)
                elif value:
                    result["features"]["building_era"] = value
                else:
                    # Extract year directly
                    year = int(match.group(1))
                    result["features"]["year_built"] = year
                break

        # Condition
        for pattern, value in cls.CONDITION_PATTERNS.items():
            if re.search(pattern, text):
                result["features"]["condition"] = value
                break

        # Orientation
        for pattern, value in cls.ORIENTATION_PATTERNS.items():
            if re.search(pattern, text):
                result["features"]["orientation"] = value
                break

        # Exposure
        for pattern, value in cls.EXPOSURE_PATTERNS.items():
            if re.search(pattern, text):
                result["features"]["exposure"] = value
                break

        # View
        for pattern, value in cls.VIEW_PATTERNS.items():
            if re.search(pattern, text):
                result["features"]["view"] = value
                break

        # Luminosity
        if re.search(r"tr[èe]s\s+lumin", text):
            result["features"]["luminosity"] = "Very bright"
        elif re.search(r"lumin|clair[eté]|belle?\s+lumi[èe]re", text):
            result["features"]["luminosity"] = "Bright"

        # Interior features
        result["features"]["has_fireplace"] = bool(re.search(r"chemin[ée]e", text))
        result["features"]["has_parquet"] = bool(re.search(r"parquet", text))
        result["features"]["has_high_ceilings"] = bool(
            re.search(r"hauteur[s]?\s+(?:sous\s+)?plafond|hauts?\s+plafond", text)
        )
        result["features"]["has_moldings"] = bool(re.search(r"moulure", text))
        result["features"]["has_equipped_kitchen"] = bool(
            re.search(r"cuisine\s+(?:am[ée]nag[ée]e\s+et\s+)?[ée]quip[ée]e", text)
        )
        result["features"]["has_separate_kitchen"] = bool(
            re.search(r"cuisine\s+(?:ind[ée]pendante|s[ée]par[ée]e)", text)
        )
        result["features"]["has_storage"] = bool(re.search(r"rangement|placard", text))
        result["features"]["has_dressing"] = bool(re.search(r"dressing", text))
        result["features"]["has_alarm"] = bool(re.search(r"alarme", text))
        result["features"]["has_intercom"] = bool(
            re.search(r"interphone|visiophone", text)
        )
        result["features"]["has_digicode"] = bool(re.search(r"digicode", text))

        # === Building Info ===

        # Copropriété lots
        lots_match = re.search(r"copropri[ée]t[ée]\s+de\s+(\d+)\s+lots?", text)
        if lots_match:
            result["building"]["total_lots"] = int(lots_match.group(1))

        # Residential lots
        res_lots_match = re.search(r"(\d+)\s+lots?\s+(?:d['\s])?habitation", text)
        if res_lots_match:
            result["building"]["residential_lots"] = int(res_lots_match.group(1))

        # Caretaker
        result["building"]["has_caretaker"] = bool(
            re.search(r"gardien|concierge|loge", text)
        )

        # Ongoing procedures
        if re.search(r"pas\s+de\s+proc[ée]dure|aucune\s+proc[ée]dure", text):
            result["building"]["has_ongoing_procedures"] = False
        elif re.search(r"proc[ée]dure\s+en\s+cours", text):
            result["building"]["has_ongoing_procedures"] = True

        # === Transport Info ===

        # Metro lines
        metro_matches = re.findall(r"m[ée]tro\s+(?:ligne\s+)?(\d+|[a-z])", text)
        if metro_matches:
            result["transport"]["metro_lines"] = list(
                set(m.upper() for m in metro_matches)
            )

        # Metro stations
        station_match = re.search(
            r"m[ée]tro\s+([A-Za-zÀ-ÿ\s\-]+?)(?:\s+\(|,|\.|$)", description
        )
        if station_match:
            station = station_match.group(1).strip()
            if len(station) > 2 and not station.lower().startswith("ligne"):
                result["transport"]["metro_stations"] = [station]

        # RER lines
        rer_matches = re.findall(r"RER\s+([A-E])", text, re.IGNORECASE)
        if rer_matches:
            result["transport"]["rer_lines"] = list(set(m.upper() for m in rer_matches))

        # Distance/time to transport - multiple patterns
        dist_patterns = [
            # "à 5 minutes du métro"
            (
                r"[àa]\s+(\d+)\s*(?:min(?:ute)?s?)\s+(?:du?\s+)?(?:m[ée]tro|transport|bus|RER|station)",
                "min",
            ),
            # "métro à 5 minutes"
            (
                r"(?:m[ée]tro|transport|station)\s+[àa]\s+(\d+)\s*(?:min(?:ute)?s?)",
                "min",
            ),
            # "à quelques pas du métro" / "à deux pas du métro" / "quelques pas de... du métro"
            (
                r"[àa]\s+(quelques|deux)\s+pas\s+(?:[^.]{0,50})?(?:du?\s+)?(?:m[ée]tro|transport|RER)",
                "steps",
            ),
            # "5 min à pied du métro"
            (
                r"(\d+)\s*(?:min(?:ute)?s?)\s+[àa]\s+pied[s]?\s+(?:du?\s+)?(?:m[ée]tro|transport|RER)",
                "min",
            ),
            # "proche du métro", "proximité du métro"
            (
                r"(prox?imit[ée]|proche)\s+(?:du?\s+)?(?:m[ée]tro|transport|RER)",
                "close",
            ),
            # "less than X minutes to Paris"
            (
                r"(?:moins\s+de\s+)?(\d+)\s*(?:min(?:ute)?s?)\s+(?:des?\s+)?(?:portes?\s+de\s+)?paris",
                "paris",
            ),
        ]

        for pattern, pattern_type in dist_patterns:
            dist_match = re.search(pattern, text)
            if dist_match:
                value = dist_match.group(1)
                if pattern_type == "min":
                    result["transport"]["distance_to_transport"] = f"{value} min walk"
                elif pattern_type == "steps":
                    if value in ["quelques", "deux"]:
                        result["transport"]["distance_to_transport"] = "2 min walk"
                elif pattern_type == "close":
                    result["transport"]["distance_to_transport"] = "Very close"
                elif pattern_type == "paris":
                    # Store Paris proximity separately or append
                    if "distance_to_transport" not in result["transport"]:
                        result["transport"][
                            "distance_to_transport"
                        ] = f"{value} min to Paris"
                break

        # === Price Info ===

        # Annual charges
        charges_match = re.search(
            r"charges?\s+annuelles?\s*[:\s]*(\d[\d\s,.]*)\s*(?:€|euros?)?",
            text,
        )
        if charges_match:
            charges_str = charges_match.group(1).replace(" ", "").replace(",", ".")
            try:
                result["price_info"]["annual_charges"] = int(float(charges_str))
            except ValueError:
                pass

        # === Agent Info ===

        # Agency name (often at start of description)
        agency_patterns = [
            r"^([A-Z][A-Za-zÀ-ÿ\s&]+(?:IMMOBILIER|IMMO|AGENCY))",
            r"([A-Z][A-Za-zÀ-ÿ\s&]+(?:IMMOBILIER|IMMO))\s+(?:vous\s+)?pr[ée]sente",
        ]
        for pattern in agency_patterns:
            agency_match = re.search(pattern, description)
            if agency_match:
                result["agent"]["agency"] = agency_match.group(1).strip()
                break

        # === Address ===

        # Street name
        street_patterns = [
            r"(?:situ[ée]e?\s+)?(?:au\s+)?(\d+[,\s]*(?:bis|ter)?\s*,?\s*rue\s+[A-Za-zÀ-ÿ\s\-]+)",
            r"rue\s+([A-Za-zÀ-ÿ\s\-]+?)(?:\s*[,.]|\s+ce\s+|\s+cet|\s+dans|\s+au|\s*$)",
        ]
        for pattern in street_patterns:
            street_match = re.search(pattern, description, re.IGNORECASE)
            if street_match:
                street = street_match.group(1).strip()
                if len(street) > 3:
                    result["address"]["street"] = street.title()
                break

        # Filter out empty dicts and None values
        return {
            k: {kk: vv for kk, vv in v.items() if vv is not None and vv != []}
            for k, v in result.items()
            if v
        }


# === Base Scraper ===


class BaseScraper(ABC):
    """Abstract base class for real estate scrapers."""

    # Override in subclasses
    SOURCE_NAME: str = "unknown"

    def __init__(
        self,
        mode: FetchMode = FetchMode.SIMPLE,
        cache_manager: Optional[CacheManager] = None,
        http_client: Optional[HTTPClient] = None,
        requests_client: Optional[RequestsClient] = None,
        cloudscraper_client: Optional[CloudscraperClient] = None,
        headless_client: Optional[HeadlessBrowserClient] = None,
    ):
        """Initialize scraper with fetch mode.

        Args:
            mode: REQUESTS (plain requests), CLOUDSCRAPER (for Cloudflare bypass),
                  SIMPLE (httpx), or HEADLESS (Playwright)
            cache_manager: Custom cache manager
            http_client: Custom HTTP client (for SIMPLE mode)
            requests_client: Custom requests client (for REQUESTS mode)
            cloudscraper_client: Custom cloudscraper client (for CLOUDSCRAPER mode)
            headless_client: Custom headless browser client (for HEADLESS mode)
        """
        self.mode = mode
        self.cache = cache_manager or CacheManager()
        self._http: Optional[HTTPClient] = http_client
        self._requests: Optional[RequestsClient] = requests_client
        self._cloudscraper: Optional[CloudscraperClient] = cloudscraper_client
        self._headless: Optional[HeadlessBrowserClient] = headless_client

    @property
    def http(self) -> HTTPClient:
        """Lazy initialization of HTTP client."""
        if self._http is None:
            self._http = HTTPClient()
        return self._http

    @property
    def requests_client(self) -> RequestsClient:
        """Lazy initialization of requests client."""
        if self._requests is None:
            self._requests = RequestsClient()
        return self._requests

    @property
    def cloudscraper_client(self) -> CloudscraperClient:
        """Lazy initialization of cloudscraper client."""
        if self._cloudscraper is None:
            self._cloudscraper = CloudscraperClient()
        return self._cloudscraper

    @property
    def headless(self) -> HeadlessBrowserClient:
        """Lazy initialization of headless browser client."""
        if self._headless is None:
            self._headless = HeadlessBrowserClient()
        return self._headless

    def _fetch_html(
        self,
        url: str,
        use_cache: bool = True,
        wait_for_selector: Optional[str] = None,
    ) -> str:
        """Fetch HTML with caching support.

        Args:
            url: URL to fetch
            use_cache: Whether to use cached HTML
            wait_for_selector: CSS selector to wait for (headless mode only)
        """
        if use_cache:
            cached = self.cache.get(url)
            if cached:
                return cached

        if self.mode == FetchMode.HEADLESS:
            html = self.headless.fetch(url, wait_for_selector=wait_for_selector)
        elif self.mode == FetchMode.CLOUDSCRAPER:
            html = self.cloudscraper_client.fetch(url)
        elif self.mode == FetchMode.REQUESTS:
            html = self.requests_client.fetch(url)
        else:  # SIMPLE mode
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

    def close(self) -> None:
        """Clean up resources."""
        self.http.close()
        if self._headless:
            self._headless.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
