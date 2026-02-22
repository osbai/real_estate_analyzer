"""Yield calculator for French real estate investment.

This module calculates:
- Gross Yield (Rendement Brut): Annual rent / Purchase price
- Net Yield (Rendement Net): (Annual rent - expenses) / Total acquisition cost

The net yield is the more accurate measure of investment return as it accounts
for all costs including notary fees, charges, and taxes.
"""

from dataclasses import dataclass, field
from typing import Optional

from .notary_fees import NotaryFeesCalculator, PropertyBuildType


@dataclass
class YieldAnalysis:
    """Complete yield analysis for a property investment."""

    # Property info
    purchase_price: int
    monthly_rent: float
    surface_area: float

    # Acquisition costs
    notary_fees: int
    total_acquisition_cost: int

    # Annual figures
    annual_rent: float
    annual_charges: int
    annual_property_tax: int  # Taxe foncière
    annual_management_fees: int  # If using property manager (~6-8%)
    annual_insurance: int  # PNO insurance
    annual_vacancy_allowance: float  # Vacancy reserve (~1 month)

    # Yields
    gross_yield: float  # Rendement brut
    net_yield: float  # Rendement net
    net_net_yield: float  # Rendement net-net (after income tax)

    # Comparisons
    rent_per_sqm: float
    market_rent_comparison: Optional[str] = None
    yield_assessment: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "purchase_price": self.purchase_price,
            "monthly_rent": self.monthly_rent,
            "surface_area": self.surface_area,
            "notary_fees": self.notary_fees,
            "total_acquisition_cost": self.total_acquisition_cost,
            "annual_rent": self.annual_rent,
            "annual_charges": self.annual_charges,
            "annual_property_tax": self.annual_property_tax,
            "annual_management_fees": self.annual_management_fees,
            "annual_insurance": self.annual_insurance,
            "annual_vacancy_allowance": self.annual_vacancy_allowance,
            "gross_yield": round(self.gross_yield, 2),
            "net_yield": round(self.net_yield, 2),
            "net_net_yield": round(self.net_net_yield, 2),
            "rent_per_sqm": round(self.rent_per_sqm, 2),
            "yield_assessment": self.yield_assessment,
        }


class YieldCalculator:
    """Calculator for rental yield metrics.

    Yield formulas:

    Gross Yield (Rendement Brut):
        = (Monthly Rent × 12) / Purchase Price × 100

    Net Yield (Rendement Net):
        = [(Annual Rent) - (Charges + Taxes + Insurance + Management)]
          / (Purchase Price + Notary Fees) × 100

    Net-Net Yield (After Tax):
        = Net Income after income tax / Total Investment × 100

    Typical yields in France:
    - Paris: 2-4%
    - Major cities (Lyon, Bordeaux, etc.): 3-5%
    - Medium cities: 5-7%
    - Small towns: 6-9%
    """

    # Average rent per m² by department (very rough estimates)
    AVG_RENTS_PER_M2 = {
        "75": 32,  # Paris
        "92": 22,  # Hauts-de-Seine
        "93": 18,  # Seine-Saint-Denis
        "94": 20,  # Val-de-Marne
        "69": 15,  # Lyon
        "13": 14,  # Marseille
        "33": 14,  # Bordeaux
        "31": 13,  # Toulouse
        "44": 13,  # Nantes
        "67": 12,  # Strasbourg
        "default": 12,
    }

    # Yield benchmarks by location type
    YIELD_BENCHMARKS = {
        "paris": (2.5, 4.0),  # min, max reasonable yield
        "major_city": (3.5, 5.5),
        "medium_city": (5.0, 7.0),
        "small_city": (6.0, 9.0),
    }

    # Default expense assumptions
    DEFAULT_MANAGEMENT_FEE_RATE = 0.07  # 7% of rent if using property manager
    DEFAULT_PNO_INSURANCE_RATE = 0.002  # 0.2% of property value
    DEFAULT_VACANCY_MONTHS = 1  # 1 month vacancy per year

    def __init__(self, notary_calculator: Optional[NotaryFeesCalculator] = None):
        """Initialize calculator.

        Args:
            notary_calculator: Calculator for notary fees, uses default if not provided
        """
        self.notary_calculator = notary_calculator or NotaryFeesCalculator()

    def estimate_market_rent(
        self,
        surface_area: float,
        postal_code: str,
        has_parking: bool = False,
        has_balcony_terrace: bool = False,
        is_furnished: bool = False,
    ) -> float:
        """Estimate market rent based on location and features.

        Args:
            surface_area: Property surface in m²
            postal_code: French postal code
            has_parking: Whether property includes parking
            has_balcony_terrace: Whether property has outdoor space
            is_furnished: Whether property is furnished

        Returns:
            Estimated monthly rent in euros
        """
        dept = postal_code[:2]
        base_rent_per_m2 = self.AVG_RENTS_PER_M2.get(
            dept, self.AVG_RENTS_PER_M2["default"]
        )

        # Apply adjustments
        rent = surface_area * base_rent_per_m2

        if has_parking:
            rent += 100  # ~100€/month for parking
        if has_balcony_terrace:
            rent *= 1.05  # 5% premium
        if is_furnished:
            rent *= 1.15  # 15% premium for furnished

        return round(rent, 0)

    def calculate_gross_yield(self, purchase_price: int, monthly_rent: float) -> float:
        """Calculate gross yield.

        Args:
            purchase_price: Property purchase price
            monthly_rent: Monthly rental income

        Returns:
            Gross yield as percentage
        """
        annual_rent = monthly_rent * 12
        return (annual_rent / purchase_price) * 100

    def calculate_net_yield(
        self,
        purchase_price: int,
        monthly_rent: float,
        notary_fees: int,
        annual_charges: int = 0,
        annual_property_tax: int = 0,
        annual_insurance: int = 0,
        annual_management_fees: int = 0,
        vacancy_months: float = 1,
    ) -> float:
        """Calculate net yield.

        Args:
            purchase_price: Property purchase price
            monthly_rent: Monthly rental income
            notary_fees: Total notary fees
            annual_charges: Annual copropriété charges (non-recoverable portion)
            annual_property_tax: Annual taxe foncière
            annual_insurance: Annual PNO insurance
            annual_management_fees: Annual property management fees
            vacancy_months: Expected vacancy per year

        Returns:
            Net yield as percentage
        """
        annual_rent = monthly_rent * 12
        vacancy_cost = monthly_rent * vacancy_months

        total_expenses = (
            annual_charges
            + annual_property_tax
            + annual_insurance
            + annual_management_fees
            + vacancy_cost
        )

        net_annual_income = annual_rent - total_expenses
        total_investment = purchase_price + notary_fees

        return (net_annual_income / total_investment) * 100

    def calculate(
        self,
        purchase_price: int,
        monthly_rent: float,
        surface_area: float,
        postal_code: str = "",
        annual_charges: Optional[int] = None,
        annual_property_tax: Optional[int] = None,
        is_neuf: bool = False,
        use_management_company: bool = False,
        description: Optional[str] = None,
        marginal_tax_rate: float = 0.30,  # Default 30% tax bracket
    ) -> YieldAnalysis:
        """Calculate complete yield analysis.

        Args:
            purchase_price: Property purchase price
            monthly_rent: Expected monthly rental income
            surface_area: Property surface area in m²
            postal_code: French postal code
            annual_charges: Annual copropriété charges (estimated if not provided)
            annual_property_tax: Annual taxe foncière (estimated if not provided)
            is_neuf: Whether property is new build
            use_management_company: Whether using property manager
            description: Listing description (for property type detection)
            marginal_tax_rate: Income tax rate for net-net calculation

        Returns:
            Complete YieldAnalysis object
        """
        # Calculate notary fees
        property_type = PropertyBuildType.NEUF if is_neuf else PropertyBuildType.ANCIEN
        notary_breakdown = self.notary_calculator.calculate(
            price=purchase_price, property_type=property_type, description=description
        )
        notary_fees = notary_breakdown.total_fees
        total_acquisition_cost = notary_breakdown.total_acquisition_cost

        # Calculate annual rent
        annual_rent = monthly_rent * 12

        # Estimate missing expenses
        if annual_charges is None:
            # Estimate charges at ~€3/m²/month (typical Parisian average)
            annual_charges = int(surface_area * 3 * 12)

        if annual_property_tax is None:
            # Estimate taxe foncière at ~1-2 months of rent equivalent
            annual_property_tax = int(monthly_rent * 1.5)

        # Calculate additional expenses
        annual_insurance = int(purchase_price * self.DEFAULT_PNO_INSURANCE_RATE)

        if use_management_company:
            annual_management_fees = int(annual_rent * self.DEFAULT_MANAGEMENT_FEE_RATE)
        else:
            annual_management_fees = 0

        vacancy_allowance = monthly_rent * self.DEFAULT_VACANCY_MONTHS

        # Calculate yields
        gross_yield = self.calculate_gross_yield(purchase_price, monthly_rent)

        net_yield = self.calculate_net_yield(
            purchase_price=purchase_price,
            monthly_rent=monthly_rent,
            notary_fees=notary_fees,
            annual_charges=annual_charges,
            annual_property_tax=annual_property_tax,
            annual_insurance=annual_insurance,
            annual_management_fees=annual_management_fees,
            vacancy_months=self.DEFAULT_VACANCY_MONTHS,
        )

        # Calculate net-net yield (after income tax)
        # Using micro-foncier regime (30% deduction) for simplicity
        taxable_income = annual_rent * 0.70  # 30% abattement
        income_tax = taxable_income * marginal_tax_rate
        social_charges = taxable_income * 0.172  # 17.2% prélèvements sociaux

        total_expenses = (
            annual_charges
            + annual_property_tax
            + annual_insurance
            + annual_management_fees
            + vacancy_allowance
            + income_tax
            + social_charges
        )

        net_net_income = annual_rent - total_expenses
        net_net_yield = (net_net_income / total_acquisition_cost) * 100

        # Calculate rent per m²
        rent_per_sqm = monthly_rent / surface_area

        # Assess yield quality
        yield_assessment = self._assess_yield(gross_yield, net_yield, postal_code)

        return YieldAnalysis(
            purchase_price=purchase_price,
            monthly_rent=monthly_rent,
            surface_area=surface_area,
            notary_fees=notary_fees,
            total_acquisition_cost=total_acquisition_cost,
            annual_rent=annual_rent,
            annual_charges=annual_charges,
            annual_property_tax=annual_property_tax,
            annual_management_fees=annual_management_fees,
            annual_insurance=annual_insurance,
            annual_vacancy_allowance=vacancy_allowance,
            gross_yield=gross_yield,
            net_yield=net_yield,
            net_net_yield=net_net_yield,
            rent_per_sqm=rent_per_sqm,
            yield_assessment=yield_assessment,
        )

    def _assess_yield(
        self, gross_yield: float, net_yield: float, postal_code: str
    ) -> str:
        """Assess yield quality based on location benchmarks.

        Args:
            gross_yield: Calculated gross yield
            net_yield: Calculated net yield
            postal_code: Property postal code

        Returns:
            Assessment string
        """
        # Determine location type
        dept = postal_code[:2] if postal_code else ""

        if dept == "75":
            location_type = "paris"
        elif dept in ["92", "93", "94", "69", "13", "33", "31", "44", "67", "59", "06"]:
            location_type = "major_city"
        elif postal_code:
            location_type = "medium_city"
        else:
            location_type = "medium_city"  # Default assumption

        min_yield, max_yield = self.YIELD_BENCHMARKS.get(
            location_type, self.YIELD_BENCHMARKS["medium_city"]
        )

        if gross_yield >= max_yield:
            return f"🟢 Excellent yield for {location_type.replace('_', ' ')} (>{max_yield}%)"
        elif gross_yield >= min_yield:
            return f"🟡 Average yield for {location_type.replace('_', ' ')} ({min_yield}-{max_yield}%)"
        else:
            return f"🔴 Below market yield for {location_type.replace('_', ' ')} (<{min_yield}%)"

    def format_analysis(self, analysis: YieldAnalysis) -> str:
        """Format yield analysis as readable text."""
        lines = [
            "📊 YIELD ANALYSIS (Analyse de Rentabilité)",
            "═" * 50,
            "",
            "INVESTMENT SUMMARY",
            "─" * 50,
            f"Purchase price: {analysis.purchase_price:,}€",
            f"Notary fees: {analysis.notary_fees:,}€",
            f"Total investment: {analysis.total_acquisition_cost:,}€",
            "",
            "RENTAL INCOME",
            "─" * 50,
            f"Monthly rent: {analysis.monthly_rent:,.0f}€",
            f"Annual rent: {analysis.annual_rent:,.0f}€",
            f"Rent per m²: {analysis.rent_per_sqm:.1f}€/m²",
            "",
            "ANNUAL EXPENSES",
            "─" * 50,
            f"Copropriété charges: {analysis.annual_charges:,}€",
            f"Taxe foncière: {analysis.annual_property_tax:,}€",
            f"PNO insurance: {analysis.annual_insurance:,}€",
            f"Management fees: {analysis.annual_management_fees:,}€",
            f"Vacancy allowance: {analysis.annual_vacancy_allowance:,.0f}€",
            "",
            "YIELDS",
            "═" * 50,
            f"Gross Yield (Rendement Brut): {analysis.gross_yield:.2f}%",
            f"Net Yield (Rendement Net): {analysis.net_yield:.2f}%",
            f"Net-Net Yield (After Tax): {analysis.net_net_yield:.2f}%",
            "",
            f"Assessment: {analysis.yield_assessment}",
            "═" * 50,
        ]
        return "\n".join(lines)
