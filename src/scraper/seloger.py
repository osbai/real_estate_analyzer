"""SeLoger.com scraper implementation."""

import json
import re
from typing import Any, Optional

from bs4 import BeautifulSoup
from src.models.listing import (
    Address,
    AgentInfo,
    EnergyClass,
    EnergyRating,
    GESClass,
    PriceInfo,
    PropertyFeatures,
    PropertyType,
)
from src.scraper.base import (
    BaseScraper,
    extract_bedrooms,
    extract_dpe_class,
    extract_floor,
    extract_ges_class,
    extract_postal_code,
    extract_price,
    extract_rooms,
    extract_surface,
    FetchMode,
    ParseError,
)


class SeLogerScraper(BaseScraper):
    """Scraper for SeLoger.com listings."""

    SOURCE_NAME = "seloger"

    # URL pattern to extract listing ID
    ID_PATTERN = re.compile(r"/annonces/[^/]+/(\d+)\.htm", re.IGNORECASE)
    # Alternative pattern for newer URLs
    ID_PATTERN_ALT = re.compile(r"/(\d{6,})(?:\.htm)?(?:\?|$)", re.IGNORECASE)

    def __init__(self, mode: FetchMode = FetchMode.SIMPLE, **kwargs):
        """Initialize SeLoger scraper.

        Args:
            mode: SIMPLE (httpx) or HEADLESS (Playwright for JS rendering)
            **kwargs: Additional arguments passed to BaseScraper
        """
        super().__init__(mode=mode, **kwargs)

    def _extract_listing_id(self, url: str) -> str:
        """Extract listing ID from SeLoger URL."""
        match = self.ID_PATTERN.search(url)
        if match:
            return match.group(1)
        match = self.ID_PATTERN_ALT.search(url)
        if match:
            return match.group(1)
        # Fallback: use URL hash
        import hashlib

        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[dict]:
        """Extract JSON-LD structured data if available."""
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                # Check for relevant types
                if isinstance(data, dict):
                    ld_type = data.get("@type", "")
                    if ld_type in (
                        "Residence",
                        "Apartment",
                        "House",
                        "Product",
                        "RealEstateListing",
                    ):
                        return data
                    # Handle @graph structure
                    if "@graph" in data:
                        for item in data["@graph"]:
                            if item.get("@type") in (
                                "Residence",
                                "Apartment",
                                "House",
                                "Product",
                            ):
                                return item
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    def _extract_initial_state(self, soup: BeautifulSoup) -> Optional[dict]:
        """Extract data from window.__INITIAL_STATE__ or similar JS variables."""
        for script in soup.find_all("script"):
            if script.string:
                # Look for various patterns of embedded data
                patterns = [
                    r"window\.__INITIAL_STATE__\s*=\s*({.+?});",
                    r"window\.initialData\s*=\s*({.+?});",
                    r"__NEXT_DATA__\s*=\s*({.+?});",
                ]
                for pattern in patterns:
                    match = re.search(pattern, script.string, re.DOTALL)
                    if match:
                        try:
                            return json.loads(match.group(1))
                        except json.JSONDecodeError:
                            continue
        return None

    def _extract_property_type(
        self, soup: BeautifulSoup, json_ld: Optional[dict]
    ) -> PropertyType:
        """Determine property type from available data."""
        type_mapping = {
            "appartement": PropertyType.APARTMENT,
            "apartment": PropertyType.APARTMENT,
            "maison": PropertyType.HOUSE,
            "house": PropertyType.HOUSE,
            "studio": PropertyType.STUDIO,
            "loft": PropertyType.LOFT,
            "duplex": PropertyType.DUPLEX,
        }

        # Try JSON-LD first
        if json_ld:
            ld_type = json_ld.get("@type", "").lower()
            for key, prop_type in type_mapping.items():
                if key in ld_type:
                    return prop_type

        # Try page content
        title_el = soup.find("h1") or soup.find(
            class_=re.compile(r"title|heading", re.I)
        )
        if title_el:
            title_text = title_el.get_text().lower()
            for key, prop_type in type_mapping.items():
                if key in title_text:
                    return prop_type

        return PropertyType.APARTMENT

    def _extract_address_data(
        self, soup: BeautifulSoup, json_ld: Optional[dict]
    ) -> dict:
        """Extract address components."""
        city = ""
        postal_code = ""
        neighborhood = None
        street = None

        # Try JSON-LD
        if json_ld:
            address_data = json_ld.get("address", {})
            if isinstance(address_data, dict):
                city = address_data.get("addressLocality", "")
                postal_code = address_data.get("postalCode", "")
                street = address_data.get("streetAddress")
                neighborhood = address_data.get("addressRegion")

        # Fallback to HTML parsing
        if not city:
            locality_el = soup.find(class_=re.compile(r"locality|location|city", re.I))
            if locality_el:
                loc_text = locality_el.get_text()
                city = loc_text.split("(")[0].strip()
                postal_code = extract_postal_code(loc_text)

        # Try breadcrumbs
        if not city:
            breadcrumbs = soup.find(class_=re.compile(r"breadcrumb", re.I))
            if breadcrumbs:
                links = breadcrumbs.find_all("a")
                for link in reversed(links):
                    text = link.get_text().strip()
                    if re.match(r"\d{5}", text) or len(text.split()) <= 3:
                        if not postal_code:
                            postal_code = extract_postal_code(text)
                        if not city and not re.match(r"^\d+$", text):
                            city = text

        # Extract department from postal code
        department = postal_code[:2] if len(postal_code) >= 2 else None

        return {
            "city": city or "Unknown",
            "postal_code": postal_code or "00000",
            "street": street,
            "neighborhood": neighborhood,
            "department": department,
        }

    def _extract_price_data(self, soup: BeautifulSoup, json_ld: Optional[dict]) -> dict:
        """Extract price information."""
        price = 0
        charges = None
        agency_fees_included = None

        # Try JSON-LD
        if json_ld:
            offers = json_ld.get("offers", {})
            if isinstance(offers, dict):
                price = int(offers.get("price", 0))
            elif json_ld.get("price"):
                price = extract_price(str(json_ld["price"]))

        # Fallback to HTML
        if not price:
            price_el = soup.find(class_=re.compile(r"price", re.I))
            if price_el:
                price = extract_price(price_el.get_text())

            # Try meta tag
            if not price:
                meta_price = soup.find("meta", property="product:price:amount")
                if meta_price:
                    price = int(float(meta_price.get("content", 0)))

        # Look for charges
        charges_el = soup.find(string=re.compile(r"charges", re.I))
        if charges_el:
            charges_text = (
                charges_el.find_parent().get_text()
                if charges_el.find_parent()
                else str(charges_el)
            )
            charges_match = re.search(
                r"(\d[\d\s]*)\s*€", charges_text.replace("\u00a0", " ")
            )
            if charges_match:
                charges = extract_price(charges_match.group(1))

        # Check for agency fees mention
        page_text = soup.get_text().lower()
        if "frais d'agence inclus" in page_text or "honoraires inclus" in page_text:
            agency_fees_included = True
        elif "hors honoraires" in page_text or "honoraires en sus" in page_text:
            agency_fees_included = False

        return {
            "price": max(price, 1),
            "charges": charges,
            "agency_fees_included": agency_fees_included,
        }

    def _extract_surface_data(
        self, soup: BeautifulSoup, json_ld: Optional[dict]
    ) -> float:
        """Extract surface area."""
        # Try JSON-LD
        if json_ld:
            floor_size = json_ld.get("floorSize")
            if floor_size:
                if isinstance(floor_size, dict):
                    value = floor_size.get("value", 0)
                else:
                    value = extract_surface(str(floor_size))
                if value:
                    return float(value)

        # Fallback to HTML
        area_el = soup.find(class_=re.compile(r"area|surface", re.I))
        if area_el:
            return extract_surface(area_el.get_text())

        # Search in feature list
        for el in soup.find_all(string=re.compile(r"\d+\s*m[²2]", re.I)):
            surface = extract_surface(str(el))
            if surface > 0:
                return surface

        return 0.0

    def _extract_features(self, soup: BeautifulSoup, json_ld: Optional[dict]) -> dict:
        """Extract property features."""
        features: dict[str, Any] = {}

        # Try JSON-LD
        if json_ld:
            if "numberOfRooms" in json_ld:
                features["rooms"] = int(json_ld["numberOfRooms"])
            if "numberOfBedrooms" in json_ld:
                features["bedrooms"] = int(json_ld["numberOfBedrooms"])
            if "numberOfBathrooms" in json_ld:
                features["bathrooms"] = int(json_ld["numberOfBathrooms"])

        # Parse feature list from HTML
        feature_containers = soup.find_all(
            class_=re.compile(r"feature|tag|criterion|caracteristique", re.I)
        )
        page_text = soup.get_text().lower()

        for container in feature_containers:
            text = container.get_text().lower()

            if "pièce" in text or "piece" in text:
                if "rooms" not in features:
                    features["rooms"] = extract_rooms(text)
            if "chambre" in text:
                if "bedrooms" not in features:
                    features["bedrooms"] = extract_bedrooms(text)
            if "salle de bain" in text or "sdb" in text:
                match = re.search(r"(\d+)", text)
                if match and "bathrooms" not in features:
                    features["bathrooms"] = int(match.group(1))
            if "étage" in text or "etage" in text:
                if "floor" not in features:
                    features["floor"] = extract_floor(text)

        # Boolean features from page text
        features["has_elevator"] = "ascenseur" in page_text
        features["has_balcony"] = "balcon" in page_text
        features["has_terrace"] = "terrasse" in page_text
        features["has_garden"] = "jardin" in page_text
        features["has_parking"] = "parking" in page_text or "garage" in page_text
        features["has_cellar"] = "cave" in page_text
        features["has_pool"] = "piscine" in page_text

        # Parking spaces
        parking_match = re.search(r"(\d+)\s*(?:parking|garage|place)", page_text)
        if parking_match:
            features["parking_spaces"] = int(parking_match.group(1))

        # Heating type
        heating_patterns = {
            "chauffage gaz": "Gas",
            "chauffage électrique": "Electric",
            "chauffage electrique": "Electric",
            "pompe à chaleur": "Heat pump",
            "pompe a chaleur": "Heat pump",
            "chauffage collectif": "Collective",
            "chauffage individuel": "Individual",
        }
        for pattern, heating_type in heating_patterns.items():
            if pattern in page_text:
                features["heating_type"] = heating_type
                break

        return features

    def _extract_energy_rating(self, soup: BeautifulSoup, json_ld: Optional[dict] = None) -> dict:  # noqa: ARG002
        """Extract DPE and GES energy ratings."""
        energy_class = EnergyClass.UNKNOWN
        ges_class = GESClass.UNKNOWN
        energy_consumption = None
        ges_emission = None

        # Look for DPE container
        dpe_container = soup.find(class_=re.compile(r"dpe|energy|diagnostic", re.I))
        if dpe_container:
            # Try to find class letter
            dpe_text = dpe_container.get_text()
            energy_class = extract_dpe_class(dpe_text)

            # Try to extract consumption value
            consumption_match = re.search(r"(\d+)\s*kWh", dpe_text)
            if consumption_match:
                energy_consumption = int(consumption_match.group(1))

        # Look for GES container
        ges_container = soup.find(class_=re.compile(r"ges|emission|co2", re.I))
        if ges_container:
            ges_text = ges_container.get_text()
            ges_class = extract_ges_class(ges_text)

            # Try to extract emission value
            emission_match = re.search(r"(\d+)\s*kg", ges_text)
            if emission_match:
                ges_emission = int(emission_match.group(1))

        # Alternative: look for data attributes
        for el in soup.find_all(attrs={"data-dpe": True}):
            dpe_value = el.get("data-dpe", "")
            if dpe_value:
                energy_class = extract_dpe_class(dpe_value)

        for el in soup.find_all(attrs={"data-ges": True}):
            ges_value = el.get("data-ges", "")
            if ges_value:
                ges_class = extract_ges_class(ges_value)

        # Search in page text for explicit mentions
        page_text = soup.get_text()
        dpe_match = re.search(
            r"(?:DPE|classe?\s+[eé]nergie)\s*[:\s]*([A-G])\b", page_text, re.I
        )
        if dpe_match and energy_class == EnergyClass.UNKNOWN:
            energy_class = extract_dpe_class(dpe_match.group(1))

        ges_match = re.search(
            r"(?:GES|classe?\s+climat)\s*[:\s]*([A-G])\b", page_text, re.I
        )
        if ges_match and ges_class == GESClass.UNKNOWN:
            ges_class = extract_ges_class(ges_match.group(1))

        return {
            "energy_class": energy_class,
            "ges_class": ges_class,
            "energy_consumption": energy_consumption,
            "ges_emission": ges_emission,
        }

    def _extract_agent_info(self, soup: BeautifulSoup) -> dict:
        """Extract agent/agency information."""
        name = None
        agency = None
        phone = None

        # Look for agency section
        agency_section = soup.find(
            class_=re.compile(r"agency|agent|contact|advertiser", re.I)
        )
        if agency_section:
            # Agency name
            agency_name_el = agency_section.find(class_=re.compile(r"name|title", re.I))
            if agency_name_el:
                agency = agency_name_el.get_text().strip()

            # Phone number
            phone_el = agency_section.find(class_=re.compile(r"phone|tel", re.I))
            if phone_el:
                phone = phone_el.get_text().strip()
                # Clean up phone number
                phone = re.sub(r"[^\d+]", "", phone)

        return {
            "name": name,
            "agency": agency,
            "phone": phone,
            "is_private_seller": False,
        }

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract listing description."""
        desc_el = soup.find(class_=re.compile(r"description|annonce-text", re.I))
        if desc_el:
            return desc_el.get_text().strip()

        # Try itemprop
        desc_el = soup.find(attrs={"itemprop": "description"})
        if desc_el:
            return desc_el.get_text().strip()

        return None

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract listing title."""
        # Try h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text().strip()

        # Try og:title
        og_title = soup.find("meta", property="og:title")
        if og_title:
            return og_title.get("content", "").strip()

        # Try title tag
        title = soup.find("title")
        if title:
            return title.get_text().split("|")[0].strip()

        return None

    def _parse(self, soup: BeautifulSoup, url: str) -> dict:
        """Parse SeLoger listing page and extract data."""
        # Try to get structured data first
        json_ld = self._extract_json_ld(soup)
        initial_state = self._extract_initial_state(soup)

        # Extract all components
        listing_id = self._extract_listing_id(url)
        property_type = self._extract_property_type(soup, json_ld)
        address_data = self._extract_address_data(soup, json_ld)
        price_data = self._extract_price_data(soup, json_ld)
        surface = self._extract_surface_data(soup, json_ld)
        features_data = self._extract_features(soup, json_ld)
        energy_data = self._extract_energy_rating(soup, json_ld)
        agent_data = self._extract_agent_info(soup)
        description = self._extract_description(soup)
        title = self._extract_title(soup)

        # Validate required fields
        if surface <= 0:
            raise ParseError(f"Could not extract surface area from {url}")
        if price_data["price"] <= 0:
            raise ParseError(f"Could not extract price from {url}")

        # Build listing data
        return {
            "id": listing_id,
            "source": self.SOURCE_NAME,
            "url": url,
            "title": title,
            "description": description,
            "property_type": property_type,
            "surface_area": surface,
            "address": Address(**address_data),
            "price_info": PriceInfo(**price_data),
            "features": PropertyFeatures(**features_data),
            "energy_rating": EnergyRating(**energy_data),
            "agent": AgentInfo(**agent_data),
            "raw_data": {"json_ld": json_ld, "initial_state": initial_state},
        }
