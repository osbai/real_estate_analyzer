"""Market analyzer for comparing listings to market data.

This module provides tools to:
- Compare a listing's price to market averages
- Estimate rental income based on market data
- Provide market context for investment decisions
- Flag underpriced or overpriced properties
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from .market_data import MarketData, CityProfile, MarketDataProvider


class PricePosition(str, Enum):
    """Position of price relative to market."""
    
    VERY_BELOW = "🟢 Significantly below market"
    BELOW = "🟢 Below market"
    AT_MARKET = "🟡 At market"
    ABOVE = "🟠 Above market"
    VERY_ABOVE = "🔴 Significantly above market"


class YieldPosition(str, Enum):
    """Position of yield relative to market."""
    
    EXCELLENT = "🟢 Excellent yield"
    GOOD = "🟢 Good yield"
    AVERAGE = "🟡 Average yield"
    BELOW_AVG = "🟠 Below average"
    POOR = "🔴 Poor yield"


@dataclass
class MarketComparison:
    """Comparison of a property to market data."""
    
    # Property data
    property_price: int
    property_price_m2: float
    property_surface: float
    location: str
    
    # Market data
    market_sale_price_m2: float
    market_rental_m2: float
    market_gross_yield: float
    
    # Comparison results
    price_difference_pct: float  # Negative = below market
    price_position: PricePosition
    
    # Rental estimates
    estimated_rent_unfurnished: float
    estimated_rent_furnished: float
    estimated_gross_yield: float
    yield_position: YieldPosition
    
    # Context
    city_profile: Optional[CityProfile] = None
    recommendation: str = ""
    flags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "property_price": self.property_price,
            "property_price_m2": round(self.property_price_m2, 0),
            "property_surface": self.property_surface,
            "location": self.location,
            "market_sale_price_m2": round(self.market_sale_price_m2, 0),
            "market_rental_m2": round(self.market_rental_m2, 1),
            "market_gross_yield": round(self.market_gross_yield, 2),
            "price_difference_pct": round(self.price_difference_pct, 1),
            "price_position": self.price_position.value,
            "estimated_rent_unfurnished": round(self.estimated_rent_unfurnished, 0),
            "estimated_rent_furnished": round(self.estimated_rent_furnished, 0),
            "estimated_gross_yield": round(self.estimated_gross_yield, 2),
            "yield_position": self.yield_position.value,
            "recommendation": self.recommendation,
            "flags": self.flags,
        }


@dataclass
class MarketContext:
    """Complete market context for a location."""
    
    location: str
    department: str
    
    # Price ranges
    sale_price_m2: float
    rental_m2_unfurnished: float
    rental_m2_furnished: float
    gross_yield: float
    
    # Location quality
    safety_score: int
    transport_score: int
    growth_potential: int
    quality_score: int
    investment_grade: str
    
    # Special factors
    grand_paris: bool = False
    olympic_impact: bool = False
    urban_renewal: bool = False
    
    # Comparisons
    nearby_cities: list[tuple[str, float, float]] = field(default_factory=list)  # name, price, yield
    
    notes: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "location": self.location,
            "department": self.department,
            "sale_price_m2": round(self.sale_price_m2, 0),
            "rental_m2_unfurnished": round(self.rental_m2_unfurnished, 1),
            "rental_m2_furnished": round(self.rental_m2_furnished, 1),
            "gross_yield": round(self.gross_yield, 2),
            "safety_score": self.safety_score,
            "transport_score": self.transport_score,
            "growth_potential": self.growth_potential,
            "quality_score": self.quality_score,
            "investment_grade": self.investment_grade,
            "grand_paris": self.grand_paris,
            "olympic_impact": self.olympic_impact,
            "urban_renewal": self.urban_renewal,
            "nearby_cities": [
                {"name": name, "price": round(price, 0), "yield": round(y, 2)}
                for name, price, y in self.nearby_cities
            ],
            "notes": self.notes,
        }


class MarketAnalyzer:
    """Analyzer for comparing properties to market data.
    
    This class provides:
    - Price comparison (is property above/below market?)
    - Rental estimation based on market data
    - Location quality assessment
    - Investment recommendations
    """
    
    # Thresholds for price position
    PRICE_THRESHOLDS = {
        "very_below": -15,  # More than 15% below market
        "below": -5,  # 5-15% below
        "above": 5,  # 5-15% above
        "very_above": 15,  # More than 15% above
    }
    
    # Thresholds for yield position (by location type)
    YIELD_THRESHOLDS = {
        "paris": {"excellent": 4.0, "good": 3.5, "average": 3.0, "below": 2.5},
        "inner_suburbs": {"excellent": 5.5, "good": 4.5, "average": 4.0, "below": 3.0},
        "outer_suburbs": {"excellent": 7.0, "good": 5.5, "average": 4.5, "below": 3.5},
    }
    
    def __init__(self, data_provider: Optional[MarketDataProvider] = None):
        """Initialize analyzer.
        
        Args:
            data_provider: Market data provider, creates default if not provided
        """
        self.data_provider = data_provider or MarketDataProvider()
    
    def _get_location_type(self, department: str) -> str:
        """Determine location type for yield thresholds."""
        if department == "75":
            return "paris"
        elif department in ["92", "93", "94"]:
            return "inner_suburbs"
        else:
            return "outer_suburbs"
    
    def _get_price_position(self, diff_pct: float) -> PricePosition:
        """Determine price position based on difference from market."""
        if diff_pct <= self.PRICE_THRESHOLDS["very_below"]:
            return PricePosition.VERY_BELOW
        elif diff_pct <= self.PRICE_THRESHOLDS["below"]:
            return PricePosition.BELOW
        elif diff_pct >= self.PRICE_THRESHOLDS["very_above"]:
            return PricePosition.VERY_ABOVE
        elif diff_pct >= self.PRICE_THRESHOLDS["above"]:
            return PricePosition.ABOVE
        else:
            return PricePosition.AT_MARKET
    
    def _get_yield_position(self, gross_yield: float, department: str) -> YieldPosition:
        """Determine yield position based on location."""
        location_type = self._get_location_type(department)
        thresholds = self.YIELD_THRESHOLDS[location_type]
        
        if gross_yield >= thresholds["excellent"]:
            return YieldPosition.EXCELLENT
        elif gross_yield >= thresholds["good"]:
            return YieldPosition.GOOD
        elif gross_yield >= thresholds["average"]:
            return YieldPosition.AVERAGE
        elif gross_yield >= thresholds["below"]:
            return YieldPosition.BELOW_AVG
        else:
            return YieldPosition.POOR
    
    def compare_to_market(
        self,
        price: int,
        surface: float,
        location: str,
        postal_code: str = "",
    ) -> Optional[MarketComparison]:
        """Compare a property to market data.
        
        Args:
            price: Property purchase price
            surface: Property surface in m²
            location: City name
            postal_code: Postal code (used for department lookup if profile not found)
            
        Returns:
            MarketComparison if market data available, None otherwise
        """
        # Get market data
        market_data = self.data_provider.get_market_data(location)
        city_profile = self.data_provider.get_city_profile(location)
        
        if not market_data:
            return None
        
        # Calculate property metrics
        price_m2 = price / surface
        
        # Calculate price difference
        price_diff_pct = ((price_m2 - market_data.sale_price_m2) / market_data.sale_price_m2) * 100
        price_position = self._get_price_position(price_diff_pct)
        
        # Estimate rents
        estimated_rent_unfurnished = market_data.estimate_rent(surface, furnished=False)
        estimated_rent_furnished = market_data.estimate_rent(surface, furnished=True)
        
        # Calculate estimated yield for this property
        estimated_gross_yield = (estimated_rent_unfurnished * 12 / price) * 100
        
        # Determine yield position
        dept = city_profile.department if city_profile else postal_code[:2]
        yield_position = self._get_yield_position(estimated_gross_yield, dept)
        
        # Generate flags and recommendations
        flags = []
        recommendation = ""
        
        if price_position in [PricePosition.VERY_BELOW, PricePosition.BELOW]:
            flags.append(f"✅ Price {abs(price_diff_pct):.0f}% below market average")
        elif price_position in [PricePosition.ABOVE, PricePosition.VERY_ABOVE]:
            flags.append(f"⚠️ Price {price_diff_pct:.0f}% above market average")
        
        if city_profile:
            if city_profile.grand_paris:
                flags.append("🚇 Grand Paris Express nearby")
            if city_profile.olympic:
                flags.append("🏅 Olympic development impact")
            if city_profile.safety <= 2:
                flags.append("⚠️ Lower safety area")
            if city_profile.growth >= 4:
                flags.append("📈 High growth potential")
        
        # Generate recommendation
        if price_position in [PricePosition.VERY_BELOW, PricePosition.BELOW] and \
           yield_position in [YieldPosition.EXCELLENT, YieldPosition.GOOD]:
            recommendation = "🟢 Strong buy signal: below market price with good yield potential"
        elif price_position == PricePosition.AT_MARKET and \
             yield_position in [YieldPosition.EXCELLENT, YieldPosition.GOOD]:
            recommendation = "🟢 Fair price with good yield - worth considering"
        elif price_position in [PricePosition.ABOVE, PricePosition.VERY_ABOVE]:
            recommendation = "🟠 Consider negotiating - price above market"
        elif yield_position in [YieldPosition.BELOW_AVG, YieldPosition.POOR]:
            recommendation = "🔴 Below average yield - may not be ideal for investment"
        else:
            recommendation = "🟡 Market rate property - standard investment"
        
        return MarketComparison(
            property_price=price,
            property_price_m2=price_m2,
            property_surface=surface,
            location=location,
            market_sale_price_m2=market_data.sale_price_m2,
            market_rental_m2=market_data.rental_price_m2,
            market_gross_yield=market_data.gross_yield,
            price_difference_pct=price_diff_pct,
            price_position=price_position,
            estimated_rent_unfurnished=estimated_rent_unfurnished,
            estimated_rent_furnished=estimated_rent_furnished,
            estimated_gross_yield=estimated_gross_yield,
            yield_position=yield_position,
            city_profile=city_profile,
            recommendation=recommendation,
            flags=flags,
        )
    
    def get_market_context(self, location: str, postal_code: str = "") -> Optional[MarketContext]:
        """Get complete market context for a location.
        
        Args:
            location: City name
            postal_code: Postal code
            
        Returns:
            MarketContext if data available, None otherwise
        """
        market_data = self.data_provider.get_market_data(location)
        city_profile = self.data_provider.get_city_profile(location)
        
        if not market_data or not city_profile:
            return None
        
        # Get nearby cities for comparison
        dept = city_profile.department
        nearby = self.data_provider.get_by_postal_code(dept)
        nearby_cities = []
        
        for profile in nearby[:5]:  # Top 5 nearby
            if profile.market_data and profile.name != location:
                nearby_cities.append((
                    profile.name,
                    profile.market_data.sale_price_m2,
                    profile.market_data.gross_yield
                ))
        
        return MarketContext(
            location=location,
            department=city_profile.department,
            sale_price_m2=market_data.sale_price_m2,
            rental_m2_unfurnished=market_data.rental_price_m2,
            rental_m2_furnished=market_data.furnished_rental_m2,
            gross_yield=market_data.gross_yield,
            safety_score=city_profile.safety,
            transport_score=city_profile.transport,
            growth_potential=city_profile.growth,
            quality_score=city_profile.quality,
            investment_grade=city_profile.get_grade(),
            grand_paris=city_profile.grand_paris,
            olympic_impact=city_profile.olympic,
            urban_renewal=city_profile.renewal,
            nearby_cities=nearby_cities,
            notes=city_profile.notes,
        )
    
    def estimate_rental_income(
        self,
        surface: float,
        location: str,
        furnished: bool = False,
        premium_adjustment: float = 0.0,
    ) -> Optional[float]:
        """Estimate monthly rental income for a property.
        
        Args:
            surface: Property surface in m²
            location: City name
            furnished: Whether to estimate furnished rent
            premium_adjustment: Additional adjustment (e.g., +0.10 for premium features)
            
        Returns:
            Estimated monthly rent, or None if no data
        """
        market_data = self.data_provider.get_market_data(location)
        if not market_data:
            return None
        
        base_rent = market_data.estimate_rent(surface, furnished=furnished)
        return base_rent * (1 + premium_adjustment)
    
    def format_comparison(self, comparison: MarketComparison) -> str:
        """Format market comparison as readable text."""
        lines = [
            "📊 MARKET COMPARISON",
            "═" * 60,
            "",
            f"Location: {comparison.location}",
            "",
            "PRICE ANALYSIS",
            "─" * 60,
            f"Your property: {comparison.property_price_m2:,.0f}€/m²",
            f"Market average: {comparison.market_sale_price_m2:,.0f}€/m²",
            f"Difference: {'+' if comparison.price_difference_pct > 0 else ''}{comparison.price_difference_pct:.1f}%",
            f"Position: {comparison.price_position.value}",
            "",
            "RENTAL ESTIMATES",
            "─" * 60,
            f"Market rent/m²: {comparison.market_rental_m2:.1f}€",
            f"Estimated unfurnished: {comparison.estimated_rent_unfurnished:,.0f}€/month",
            f"Estimated furnished: {comparison.estimated_rent_furnished:,.0f}€/month",
            "",
            "YIELD ANALYSIS",
            "─" * 60,
            f"Market gross yield: {comparison.market_gross_yield:.2f}%",
            f"Your estimated yield: {comparison.estimated_gross_yield:.2f}%",
            f"Position: {comparison.yield_position.value}",
        ]
        
        if comparison.flags:
            lines.extend([
                "",
                "FLAGS",
                "─" * 60,
            ])
            for flag in comparison.flags:
                lines.append(f"  {flag}")
        
        if comparison.city_profile:
            profile = comparison.city_profile
            lines.extend([
                "",
                "LOCATION PROFILE",
                "─" * 60,
                f"Safety: {'★' * profile.safety}{'☆' * (5-profile.safety)} ({profile.safety}/5)",
                f"Transport: {'★' * profile.transport}{'☆' * (5-profile.transport)} ({profile.transport}/5)",
                f"Growth: {'★' * profile.growth}{'☆' * (5-profile.growth)} ({profile.growth}/5)",
                f"Quality: {'★' * profile.quality}{'☆' * (5-profile.quality)} ({profile.quality}/5)",
                f"Investment Grade: {profile.get_grade()}",
            ])
            if profile.notes:
                lines.append(f"Notes: {profile.notes}")
        
        lines.extend([
            "",
            "═" * 60,
            f"💡 {comparison.recommendation}",
            "═" * 60,
        ])
        
        return "\n".join(lines)
    
    def format_context(self, context: MarketContext) -> str:
        """Format market context as readable text."""
        lines = [
            "🏙️ MARKET CONTEXT",
            "═" * 60,
            f"Location: {context.location} ({context.department})",
            "",
            "MARKET PRICES",
            "─" * 60,
            f"Sale price: {context.sale_price_m2:,.0f}€/m²",
            f"Rent (unfurnished): {context.rental_m2_unfurnished:.1f}€/m²/month",
            f"Rent (furnished): {context.rental_m2_furnished:.1f}€/m²/month",
            f"Gross yield: {context.gross_yield:.2f}%",
            "",
            "LOCATION SCORES",
            "─" * 60,
            f"Safety: {context.safety_score}/5",
            f"Transport: {context.transport_score}/5",
            f"Growth potential: {context.growth_potential}/5",
            f"Quality of life: {context.quality_score}/5",
            f"Investment grade: {context.investment_grade}",
            "",
            "SPECIAL FACTORS",
            "─" * 60,
        ]
        
        factors = []
        if context.grand_paris:
            factors.append("🚇 Grand Paris Express")
        if context.olympic_impact:
            factors.append("🏅 Olympic impact")
        if context.urban_renewal:
            factors.append("🏗️ Urban renewal")
        
        if factors:
            for f in factors:
                lines.append(f"  {f}")
        else:
            lines.append("  None")
        
        if context.nearby_cities:
            lines.extend([
                "",
                "NEARBY COMPARISONS",
                "─" * 60,
            ])
            for name, price, y in context.nearby_cities:
                lines.append(f"  {name}: {price:,.0f}€/m² ({y:.1f}% yield)")
        
        if context.notes:
            lines.extend([
                "",
                f"📝 {context.notes}",
            ])
        
        lines.append("═" * 60)
        
        return "\n".join(lines)
