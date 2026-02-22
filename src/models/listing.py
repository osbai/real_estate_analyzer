"""Data models for real estate listings, optimized for French property market."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, computed_field


class PropertyType(str, Enum):
    """Type of property."""
    APARTMENT = "apartment"
    HOUSE = "house"
    STUDIO = "studio"
    LOFT = "loft"
    DUPLEX = "duplex"
    OTHER = "other"


class EnergyClass(str, Enum):
    """French DPE energy classification (A to G)."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    UNKNOWN = "unknown"


class GESClass(str, Enum):
    """French GES (greenhouse gas emissions) classification."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    UNKNOWN = "unknown"


class Address(BaseModel):
    """Property address information."""
    street: Optional[str] = None
    city: str
    postal_code: str
    neighborhood: Optional[str] = None
    department: Optional[str] = None
    region: Optional[str] = None
    country: str = "France"
    
    @computed_field
    @property
    def full_address(self) -> str:
        """Return formatted full address."""
        parts = [self.street, f"{self.postal_code} {self.city}"]
        return ", ".join(p for p in parts if p)


class EnergyRating(BaseModel):
    """French DPE (Diagnostic de Performance Énergétique) information."""
    energy_class: EnergyClass = EnergyClass.UNKNOWN
    energy_consumption: Optional[int] = Field(
        default=None, description="kWh/m²/year"
    )
    ges_class: GESClass = GESClass.UNKNOWN
    ges_emission: Optional[int] = Field(
        default=None, description="kgCO2/m²/year"
    )


class PropertyFeatures(BaseModel):
    """Detailed property features and amenities."""
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    rooms: Optional[int] = Field(default=None, description="Total number of rooms (pièces)")
    floor: Optional[int] = Field(default=None, description="Floor number")
    total_floors: Optional[int] = Field(default=None, description="Total floors in building")
    has_elevator: Optional[bool] = None
    has_balcony: Optional[bool] = None
    has_terrace: Optional[bool] = None
    has_garden: Optional[bool] = None
    has_parking: Optional[bool] = None
    parking_spaces: Optional[int] = None
    has_cellar: Optional[bool] = None
    has_pool: Optional[bool] = None
    has_fireplace: Optional[bool] = None
    has_parquet: Optional[bool] = None
    has_high_ceilings: Optional[bool] = None
    has_moldings: Optional[bool] = None
    has_equipped_kitchen: Optional[bool] = None
    has_separate_kitchen: Optional[bool] = None
    has_storage: Optional[bool] = None
    has_dressing: Optional[bool] = None
    has_alarm: Optional[bool] = None
    has_intercom: Optional[bool] = None
    has_digicode: Optional[bool] = None
    orientation: Optional[str] = Field(default=None, description="e.g., 'South', 'South-West'")
    exposure: Optional[str] = Field(default=None, description="e.g., 'Double', 'Triple', 'Traversant'")
    view: Optional[str] = Field(default=None, description="e.g., 'Garden', 'Street', 'Courtyard'")
    luminosity: Optional[str] = Field(default=None, description="e.g., 'Very bright', 'Bright'")
    heating_type: Optional[str] = Field(default=None, description="e.g., 'Gas', 'Electric', 'Heat pump'")
    condition: Optional[str] = Field(default=None, description="e.g., 'New', 'Renovated', 'To refresh'")
    year_built: Optional[int] = None
    building_era: Optional[str] = Field(default=None, description="e.g., 'Haussmannien', 'Années 30', 'Modern'")
    last_renovation: Optional[int] = None


class BuildingInfo(BaseModel):
    """Information about the building/copropriété."""
    total_lots: Optional[int] = Field(default=None, description="Total lots in copropriété")
    residential_lots: Optional[int] = Field(default=None, description="Residential lots count")
    has_caretaker: Optional[bool] = None
    has_ongoing_procedures: Optional[bool] = Field(default=None, description="Legal procedures in progress")
    building_condition: Optional[str] = None


class TransportInfo(BaseModel):
    """Public transport proximity information."""
    metro_lines: list[str] = Field(default_factory=list, description="Nearby metro lines")
    metro_stations: list[str] = Field(default_factory=list, description="Nearby metro stations")
    bus_lines: list[str] = Field(default_factory=list, description="Nearby bus lines")
    rer_lines: list[str] = Field(default_factory=list, description="Nearby RER lines")
    tram_lines: list[str] = Field(default_factory=list, description="Nearby tram lines")
    distance_to_transport: Optional[str] = Field(default=None, description="e.g., '2 min walk'")


class PriceInfo(BaseModel):
    """Price and financial information."""
    price: int = Field(description="Listing price in euros")
    price_per_sqm: Optional[float] = Field(default=None, description="Price per square meter")
    charges: Optional[int] = Field(default=None, description="Monthly co-ownership charges")
    annual_charges: Optional[int] = Field(default=None, description="Annual co-ownership charges")
    property_tax: Optional[int] = Field(default=None, description="Annual property tax (taxe foncière)")
    agency_fees_included: Optional[bool] = Field(default=None, description="Whether price includes agency fees")
    agency_fees: Optional[int] = Field(default=None, description="Agency fees amount if separate")
    notary_fees_estimate: Optional[int] = Field(default=None, description="Estimated notary fees")
    
    @computed_field
    @property
    def total_acquisition_cost(self) -> int:
        """Estimate total acquisition cost including fees."""
        total = self.price
        if self.notary_fees_estimate:
            total += self.notary_fees_estimate
        elif not self.agency_fees_included:
            # Estimate notary fees at ~8% for older properties
            total += int(self.price * 0.08)
        if self.agency_fees and not self.agency_fees_included:
            total += self.agency_fees
        return total


class AgentInfo(BaseModel):
    """Real estate agent/agency information."""
    name: Optional[str] = None
    agency: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_private_seller: bool = Field(default=False, description="True if PAP (particulier à particulier)")


class Listing(BaseModel):
    """Complete real estate listing data model."""
    # Identification
    id: str = Field(description="Unique listing ID from source")
    source: str = Field(description="Source website (e.g., 'seloger', 'pap')")
    url: HttpUrl
    
    # Basic info
    title: Optional[str] = None
    description: Optional[str] = None
    property_type: PropertyType = PropertyType.APARTMENT
    
    # Size
    surface_area: float = Field(description="Living area in square meters")
    lot_size: Optional[float] = Field(default=None, description="Land area in sqm (for houses)")
    carrez_area: Optional[float] = Field(default=None, description="Carrez law area in sqm")
    
    # Location
    address: Address
    
    # Financial
    price_info: PriceInfo
    
    # Features
    features: PropertyFeatures = Field(default_factory=PropertyFeatures)
    
    # Building info
    building: BuildingInfo = Field(default_factory=BuildingInfo)
    
    # Transport
    transport: TransportInfo = Field(default_factory=TransportInfo)
    
    # Energy
    energy_rating: EnergyRating = Field(default_factory=EnergyRating)
    
    # Agent
    agent: AgentInfo = Field(default_factory=AgentInfo)
    
    # Metadata
    published_date: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    scraped_at: datetime = Field(default_factory=datetime.now)
    
    # Raw data for debugging
    raw_data: Optional[dict] = Field(default=None, exclude=True)
    
    @computed_field
    @property
    def price_per_sqm(self) -> float:
        """Calculate price per square meter."""
        return round(self.price_info.price / self.surface_area, 2)
    
    def summary(self) -> str:
        """Return a brief summary of the listing."""
        rooms = f"{self.features.rooms}p" if self.features.rooms else ""
        beds = f"{self.features.bedrooms}ch" if self.features.bedrooms else ""
        features = " ".join(filter(None, [rooms, beds]))
        
        return (
            f"{self.property_type.value.title()} {features} - {self.surface_area}m² - "
            f"{self.price_info.price:,}€ ({self.price_per_sqm:,.0f}€/m²) - "
            f"{self.address.city}"
        )
