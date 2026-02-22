"""PAP.fr (Particulier à Particulier) scraper implementation."""

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


class PAPScraper(BaseScraper):
    """Scraper for PAP.fr listings (private sellers)."""

    SOURCE_NAME = "pap"

    # URL pattern to extract listing ID: /annonces/appartement-paris-11e-r123456789
    ID_PATTERN = re.compile(r"-r(\d+)(?:\?|$|/)", re.IGNORECASE)
    # Alternative pattern
    ID_PATTERN_ALT = re.compile(r"/(\d{7,})(?:\?|$)", re.IGNORECASE)

    def __init__(self, mode: FetchMode = FetchMode.SIMPLE, **kwargs):
        """Initialize PAP scraper.

        Args:
            mode: SIMPLE (httpx) or HEADLESS (Playwright for JS rendering)
            **kwargs: Additional arguments passed to BaseScraper
        """
        super().__init__(mode=mode, **kwargs)

    def _extract_listing_id(self, url: str) -> str:
        """Extract listing ID from PAP URL."""
        match = self.ID_PATTERN.search(url)
        if match:
            return match.group(1)
        match = self.ID_PATTERN_ALT.search(url)
        if match:
            return match.group(1)
        # Fallback: use URL hash
        import hashlib

        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _extract_property_type(self, soup: BeautifulSoup) -> PropertyType:
        """Determine property type from page content."""
        type_mapping = {
            "appartement": PropertyType.APARTMENT,
            "maison": PropertyType.HOUSE,
            "studio": PropertyType.STUDIO,
            "loft": PropertyType.LOFT,
            "duplex": PropertyType.DUPLEX,
        }

        # Try page title
        title_el = soup.find("h1") or soup.find(
            class_=re.compile(r"item-title|title", re.I)
        )
        if title_el:
            title_text = title_el.get_text().lower()
            for key, prop_type in type_mapping.items():
                if key in title_text:
                    return prop_type

        # Try breadcrumb
        breadcrumb = soup.find(class_=re.compile(r"breadcrumb", re.I))
        if breadcrumb:
            breadcrumb_text = breadcrumb.get_text().lower()
            for key, prop_type in type_mapping.items():
                if key in breadcrumb_text:
                    return prop_type

        # Try URL
        url_text = soup.find("link", rel="canonical")
        if url_text:
            href = url_text.get("href", "").lower()
            for key, prop_type in type_mapping.items():
                if key in href:
                    return prop_type

        return PropertyType.APARTMENT

    def _extract_address_data(self, soup: BeautifulSoup) -> dict:
        """Extract address components from PAP listing."""
        city = ""
        postal_code = ""
        neighborhood = None
        street = None

        # PAP typically shows location in the heading or breadcrumb
        location_el = soup.find(
            class_=re.compile(r"item-geoloc|location|locality", re.I)
        )
        if location_el:
            loc_text = location_el.get_text()
            # Format is often "Paris 11e (75011)" or "Montrouge (92120)"
            postal_code = extract_postal_code(loc_text)
            # Extract city name before postal code
            city_match = re.match(r"([^(]+)", loc_text)
            if city_match:
                city = city_match.group(1).strip()

        # Try breadcrumb
        if not city:
            breadcrumb = soup.find(class_=re.compile(r"breadcrumb", re.I))
            if breadcrumb:
                links = breadcrumb.find_all("a")
                for link in reversed(links):
                    text = link.get_text().strip()
                    if extract_postal_code(text):
                        postal_code = extract_postal_code(text)
                    elif len(text.split()) <= 3 and not re.match(r"^\d+$", text):
                        city = text

        # Try title
        if not city:
            title = soup.find("h1")
            if title:
                title_text = title.get_text()
                # Look for city pattern: "Appartement 3 pièces Paris 11e"
                city_match = re.search(
                    r"(?:à|a)\s+([A-Za-zÀ-ÿ\-\s]+?)(?:\s+\d|$|\()", title_text
                )
                if city_match:
                    city = city_match.group(1).strip()
                # Also check for arrondissement in Paris
                arrond_match = re.search(r"Paris\s*(\d{1,2})e?", title_text, re.I)
                if arrond_match:
                    city = f"Paris {arrond_match.group(1)}e"
                    if not postal_code:
                        # Generate Paris postal code
                        arrond = int(arrond_match.group(1))
                        postal_code = f"750{arrond:02d}"

        # Extract department from postal code
        department = postal_code[:2] if len(postal_code) >= 2 else None

        return {
            "city": city or "Unknown",
            "postal_code": postal_code or "00000",
            "street": street,
            "neighborhood": neighborhood,
            "department": department,
        }

    def _extract_price_data(self, soup: BeautifulSoup) -> dict:
        """Extract price information from PAP listing."""
        price = 0
        charges = None

        # PAP has clear price display
        price_el = soup.find(class_=re.compile(r"item-price|price", re.I))
        if price_el:
            price_text = price_el.get_text()
            price = extract_price(price_text)

            # Check for "charges comprises" or separate charges
            if "cc" in price_text.lower() or "charges comprises" in price_text.lower():
                # Price includes charges - we don't separate them
                pass

        # Try to find charges elsewhere
        charges_el = soup.find(string=re.compile(r"charges", re.I))
        if charges_el:
            parent = charges_el.find_parent()
            if parent:
                charges_text = parent.get_text()
                charges_match = re.search(
                    r"(\d[\d\s]*)\s*€?\s*/?\s*mois", charges_text.replace("\u00a0", " ")
                )
                if charges_match:
                    charges = extract_price(charges_match.group(1))

        # Fallback to meta tag
        if not price:
            meta_price = soup.find("meta", property="product:price:amount")
            if meta_price:
                price = int(float(meta_price.get("content", 0)))

        return {
            "price": max(price, 1),
            "charges": charges,
            "agency_fees_included": True,  # PAP = no agency fees (private sellers)
        }

    def _extract_surface_data(self, soup: BeautifulSoup) -> float:
        """Extract surface area from PAP listing."""
        # PAP shows surface in features or title
        for el in soup.find_all(class_=re.compile(r"item-tags|features|surface", re.I)):
            text = el.get_text()
            if "m²" in text or "m2" in text:
                surface = extract_surface(text)
                if surface > 0:
                    return surface

        # Try finding in any element with m²
        for el in soup.find_all(string=re.compile(r"\d+\s*m[²2]", re.I)):
            surface = extract_surface(str(el))
            if surface > 0:
                return surface

        # Try title
        title = soup.find("h1")
        if title:
            surface = extract_surface(title.get_text())
            if surface > 0:
                return surface

        return 0.0

    def _extract_features(self, soup: BeautifulSoup) -> dict:
        """Extract property features from PAP listing."""
        features: dict[str, Any] = {}

        # PAP has feature tags/items
        feature_sections = soup.find_all(
            class_=re.compile(r"item-tags|features|caracteristiques", re.I)
        )
        page_text = soup.get_text().lower()

        for section in feature_sections:
            items = section.find_all(["li", "span", "div"])
            for item in items:
                text = item.get_text().lower()

                if "pièce" in text:
                    if "rooms" not in features:
                        features["rooms"] = extract_rooms(text)
                if "chambre" in text:
                    if "bedrooms" not in features:
                        features["bedrooms"] = extract_bedrooms(text)
                if "salle" in text and ("bain" in text or "eau" in text):
                    match = re.search(r"(\d+)", text)
                    if match and "bathrooms" not in features:
                        features["bathrooms"] = int(match.group(1))
                if "étage" in text or "etage" in text:
                    if "floor" not in features:
                        features["floor"] = extract_floor(text)

        # Also try the title for room count
        title = soup.find("h1")
        if title:
            title_text = title.get_text()
            if "rooms" not in features:
                features["rooms"] = extract_rooms(title_text)

        # Boolean features from page text
        features["has_elevator"] = "ascenseur" in page_text
        features["has_balcony"] = "balcon" in page_text
        features["has_terrace"] = "terrasse" in page_text
        features["has_garden"] = "jardin" in page_text
        features["has_parking"] = (
            "parking" in page_text
            or "garage" in page_text
            or "stationnement" in page_text
        )
        features["has_cellar"] = "cave" in page_text
        features["has_pool"] = "piscine" in page_text

        # Parking spaces
        parking_match = re.search(r"(\d+)\s*(?:parking|garage|place)", page_text)
        if parking_match:
            features["parking_spaces"] = int(parking_match.group(1))

        # Heating type
        heating_patterns = {
            "chauffage gaz": "Gas",
            "gaz de ville": "Gas",
            "chauffage électrique": "Electric",
            "chauffage electrique": "Electric",
            "radiateurs électriques": "Electric",
            "pompe à chaleur": "Heat pump",
            "chauffage collectif": "Collective",
            "chauffage individuel": "Individual",
        }
        for pattern, heating_type in heating_patterns.items():
            if pattern in page_text:
                features["heating_type"] = heating_type
                break

        return features

    def _extract_energy_rating(self, soup: BeautifulSoup) -> dict:
        """Extract DPE and GES energy ratings from PAP listing."""
        energy_class = EnergyClass.UNKNOWN
        ges_class = GESClass.UNKNOWN
        energy_consumption = None
        ges_emission = None

        # PAP shows DPE/GES in dedicated sections
        dpe_section = soup.find(class_=re.compile(r"dpe|energy|diagnostic", re.I))
        if dpe_section:
            dpe_text = dpe_section.get_text()
            energy_class = extract_dpe_class(dpe_text)

            # Look for consumption value
            consumption_match = re.search(r"(\d+)\s*kWh", dpe_text)
            if consumption_match:
                energy_consumption = int(consumption_match.group(1))

        # GES section
        ges_section = soup.find(class_=re.compile(r"ges|emission", re.I))
        if ges_section:
            ges_text = ges_section.get_text()
            ges_class = extract_ges_class(ges_text)

            emission_match = re.search(r"(\d+)\s*kg", ges_text)
            if emission_match:
                ges_emission = int(emission_match.group(1))

        # Look for data attributes (common pattern)
        for el in soup.find_all(attrs={"data-dpe": True}):
            energy_class = extract_dpe_class(el.get("data-dpe", ""))

        for el in soup.find_all(attrs={"data-ges": True}):
            ges_class = extract_ges_class(el.get("data-ges", ""))

        # Alternative: look in image alt text or class names
        for img in soup.find_all("img"):
            alt = img.get("alt", "").lower()
            src = img.get("src", "").lower()
            _ = " ".join(img.get("class", []))  # Reserved for future use

            if "dpe" in alt or "dpe" in src or "energie" in alt:
                # Try to extract letter from filename or alt
                letter_match = re.search(r"[_-]([a-g])(?:\.|_|$)", src, re.I)
                if letter_match and energy_class == EnergyClass.UNKNOWN:
                    energy_class = extract_dpe_class(letter_match.group(1))

            if "ges" in alt or "ges" in src or "climat" in alt:
                letter_match = re.search(r"[_-]([a-g])(?:\.|_|$)", src, re.I)
                if letter_match and ges_class == GESClass.UNKNOWN:
                    ges_class = extract_ges_class(letter_match.group(1))

        # Search in page text for explicit mentions
        page_text = soup.get_text()
        if energy_class == EnergyClass.UNKNOWN:
            dpe_match = re.search(
                r"(?:DPE|diagnostic|classe?\s+[eé]nergie)\s*[:\s]*([A-G])\b",
                page_text,
                re.I,
            )
            if dpe_match:
                energy_class = extract_dpe_class(dpe_match.group(1))

        if ges_class == GESClass.UNKNOWN:
            ges_match = re.search(
                r"(?:GES|classe?\s+climat|[eé]mission)\s*[:\s]*([A-G])\b",
                page_text,
                re.I,
            )
            if ges_match:
                ges_class = extract_ges_class(ges_match.group(1))

        return {
            "energy_class": energy_class,
            "ges_class": ges_class,
            "energy_consumption": energy_consumption,
            "ges_emission": ges_emission,
        }

    def _extract_agent_info(self, soup: BeautifulSoup) -> dict:
        """Extract seller information from PAP listing.

        Note: PAP = Particulier à Particulier, so sellers are always private.
        """
        name = None
        phone = None

        # Look for contact section
        contact_section = soup.find(
            class_=re.compile(r"contact|seller|owner|advertiser", re.I)
        )
        if contact_section:
            # Try to find name
            name_el = contact_section.find(class_=re.compile(r"name", re.I))
            if name_el:
                name = name_el.get_text().strip()

            # Phone (often hidden until clicked, but might be visible)
            phone_el = contact_section.find(class_=re.compile(r"phone|tel", re.I))
            if phone_el:
                phone = phone_el.get_text().strip()
                phone = re.sub(r"[^\d+]", "", phone)

        return {
            "name": name,
            "agency": None,  # PAP = private sellers
            "phone": phone,
            "is_private_seller": True,  # Always true for PAP
        }

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract listing description from PAP."""
        desc_el = soup.find(
            class_=re.compile(r"item-description|description|annonce-text", re.I)
        )
        if desc_el:
            return desc_el.get_text().strip()

        # Try itemprop
        desc_el = soup.find(attrs={"itemprop": "description"})
        if desc_el:
            return desc_el.get_text().strip()

        return None

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract listing title from PAP."""
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
            # PAP titles often have "PAP" at the end
            return title.get_text().split(" - PAP")[0].strip()

        return None

    def _parse(self, soup: BeautifulSoup, url: str) -> dict:
        """Parse PAP listing page and extract data."""
        # Extract all components
        listing_id = self._extract_listing_id(url)
        property_type = self._extract_property_type(soup)
        address_data = self._extract_address_data(soup)
        price_data = self._extract_price_data(soup)
        surface = self._extract_surface_data(soup)
        features_data = self._extract_features(soup)
        energy_data = self._extract_energy_rating(soup)
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
        }
