"""Investment analyzer combining yield, notary fees, and cash flow analysis.

This module provides a unified interface for analyzing French real estate
investments by combining all financial metrics into a single report.
"""

from dataclasses import dataclass, field
from typing import Optional

from .notary_fees import NotaryFeesCalculator, NotaryFeesBreakdown, PropertyBuildType
from .yield_calculator import YieldCalculator, YieldAnalysis
from .cashflow import CashFlowModeler, CashFlowAnalysis, LoanComparison


@dataclass
class InvestmentReport:
    """Comprehensive investment analysis report."""
    
    # Property summary
    purchase_price: int
    surface_area: float
    city: str
    postal_code: str
    
    # Monthly rent (actual or estimated)
    monthly_rent: float
    rent_is_estimated: bool
    
    # Component analyses
    notary_fees: NotaryFeesBreakdown
    yield_analysis: YieldAnalysis
    cash_flow_default: CashFlowAnalysis
    loan_comparison: Optional[LoanComparison] = None
    
    # Summary metrics
    total_acquisition_cost: int = 0
    gross_yield: float = 0.0
    net_yield: float = 0.0
    monthly_cash_flow: float = 0.0
    cash_flow_status: str = ""
    
    # Investment verdict
    verdict: str = ""
    recommendations: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "purchase_price": self.purchase_price,
            "surface_area": self.surface_area,
            "city": self.city,
            "postal_code": self.postal_code,
            "monthly_rent": self.monthly_rent,
            "rent_is_estimated": self.rent_is_estimated,
            "notary_fees": self.notary_fees.to_dict(),
            "yield_analysis": self.yield_analysis.to_dict(),
            "cash_flow": self.cash_flow_default.to_dict(),
            "total_acquisition_cost": self.total_acquisition_cost,
            "gross_yield": round(self.gross_yield, 2),
            "net_yield": round(self.net_yield, 2),
            "monthly_cash_flow": round(self.monthly_cash_flow, 2),
            "cash_flow_status": self.cash_flow_status,
            "verdict": self.verdict,
            "recommendations": self.recommendations,
        }


class InvestmentAnalyzer:
    """Unified investment analyzer for French real estate.
    
    This class combines:
    - Notary fees calculation
    - Yield analysis (gross, net, net-net)
    - Cash flow modeling with loan scenarios
    
    It provides a complete investment picture to help decide if a property
    is worth purchasing as a rental investment.
    """
    
    def __init__(
        self,
        notary_calculator: Optional[NotaryFeesCalculator] = None,
        yield_calculator: Optional[YieldCalculator] = None,
        cashflow_modeler: Optional[CashFlowModeler] = None,
    ):
        """Initialize analyzer with component calculators."""
        self.notary_calculator = notary_calculator or NotaryFeesCalculator()
        self.yield_calculator = yield_calculator or YieldCalculator(
            notary_calculator=self.notary_calculator
        )
        self.cashflow_modeler = cashflow_modeler or CashFlowModeler()
    
    def analyze(
        self,
        purchase_price: int,
        surface_area: float,
        city: str = "",
        postal_code: str = "",
        monthly_rent: Optional[float] = None,
        annual_charges: Optional[int] = None,
        annual_property_tax: Optional[int] = None,
        description: Optional[str] = None,
        title: Optional[str] = None,
        year_built: Optional[int] = None,
        condition: Optional[str] = None,
        has_parking: bool = False,
        has_balcony_terrace: bool = False,
        down_payment_percentage: float = 20.0,
        loan_duration_years: int = 25,
        interest_rate: Optional[float] = None,
        include_loan_comparison: bool = True,
        use_management_company: bool = False,
    ) -> InvestmentReport:
        """Analyze a property as a rental investment.
        
        Args:
            purchase_price: Property purchase price
            surface_area: Property surface area in m²
            city: City name
            postal_code: French postal code
            monthly_rent: Expected monthly rent (estimated if not provided)
            annual_charges: Annual copropriété charges
            annual_property_tax: Annual taxe foncière
            description: Listing description (for property type detection)
            title: Listing title
            year_built: Year property was built
            condition: Property condition
            has_parking: Whether property includes parking
            has_balcony_terrace: Whether property has outdoor space
            down_payment_percentage: Default down payment percentage
            loan_duration_years: Default loan duration
            interest_rate: Annual interest rate (uses market rate if not provided)
            include_loan_comparison: Whether to include multiple loan scenarios
            use_management_company: Whether using property manager
            
        Returns:
            Complete InvestmentReport
        """
        # Detect property type for notary fees
        property_type = self.notary_calculator.detect_property_type(
            description=description,
            title=title,
            year_built=year_built,
            condition=condition
        )
        is_neuf = property_type == PropertyBuildType.NEUF
        
        # Calculate notary fees
        notary_fees = self.notary_calculator.calculate(
            price=purchase_price,
            property_type=property_type,
            description=description,
            title=title,
            year_built=year_built,
            condition=condition
        )
        
        # Estimate rent if not provided
        rent_is_estimated = monthly_rent is None
        if rent_is_estimated:
            monthly_rent = self.yield_calculator.estimate_market_rent(
                surface_area=surface_area,
                postal_code=postal_code,
                has_parking=has_parking,
                has_balcony_terrace=has_balcony_terrace,
            )
        
        # Calculate yield analysis
        yield_analysis = self.yield_calculator.calculate(
            purchase_price=purchase_price,
            monthly_rent=monthly_rent,
            surface_area=surface_area,
            postal_code=postal_code,
            annual_charges=annual_charges,
            annual_property_tax=annual_property_tax,
            is_neuf=is_neuf,
            use_management_company=use_management_company,
            description=description,
        )
        
        # Calculate cash flow with default parameters
        cash_flow_default = self.cashflow_modeler.calculate(
            purchase_price=purchase_price,
            monthly_rent=monthly_rent,
            down_payment_percentage=down_payment_percentage,
            interest_rate=interest_rate,
            duration_years=loan_duration_years,
            notary_fees=notary_fees.total_fees,
            annual_charges=annual_charges,
            annual_property_tax=annual_property_tax,
            surface_area=surface_area,
            use_management_company=use_management_company,
            is_neuf=is_neuf,
        )
        
        # Compare loan scenarios if requested
        loan_comparison = None
        if include_loan_comparison:
            loan_comparison = self.cashflow_modeler.compare_scenarios(
                purchase_price=purchase_price,
                monthly_rent=monthly_rent,
                durations=[15, 20, 25],
                down_payment_percentages=[10, 20, 30],
                notary_fees=notary_fees.total_fees,
                annual_charges=annual_charges,
                annual_property_tax=annual_property_tax,
                surface_area=surface_area,
                use_management_company=use_management_company,
                is_neuf=is_neuf,
            )
        
        # Generate verdict and recommendations
        verdict, recommendations = self._generate_verdict(
            yield_analysis=yield_analysis,
            cash_flow=cash_flow_default,
            loan_comparison=loan_comparison,
            property_type=property_type,
            rent_is_estimated=rent_is_estimated,
        )
        
        return InvestmentReport(
            purchase_price=purchase_price,
            surface_area=surface_area,
            city=city,
            postal_code=postal_code,
            monthly_rent=monthly_rent,
            rent_is_estimated=rent_is_estimated,
            notary_fees=notary_fees,
            yield_analysis=yield_analysis,
            cash_flow_default=cash_flow_default,
            loan_comparison=loan_comparison,
            total_acquisition_cost=notary_fees.total_acquisition_cost,
            gross_yield=yield_analysis.gross_yield,
            net_yield=yield_analysis.net_yield,
            monthly_cash_flow=cash_flow_default.monthly_cash_flow,
            cash_flow_status=cash_flow_default.cash_flow_status.value,
            verdict=verdict,
            recommendations=recommendations,
        )
    
    def _generate_verdict(
        self,
        yield_analysis: YieldAnalysis,
        cash_flow: CashFlowAnalysis,
        loan_comparison: Optional[LoanComparison],
        property_type: PropertyBuildType,
        rent_is_estimated: bool,
    ) -> tuple[str, list[str]]:
        """Generate investment verdict and recommendations."""
        recommendations = []
        
        # Yield assessment
        if yield_analysis.gross_yield >= 6:
            yield_verdict = "Excellent"
        elif yield_analysis.gross_yield >= 4:
            yield_verdict = "Good"
        elif yield_analysis.gross_yield >= 3:
            yield_verdict = "Average"
        else:
            yield_verdict = "Below average"
        
        # Cash flow assessment
        if cash_flow.monthly_cash_flow > 100:
            cf_verdict = "generates positive cash flow"
        elif cash_flow.monthly_cash_flow >= -50:
            cf_verdict = "breaks even"
        else:
            cf_verdict = f"requires {abs(cash_flow.monthly_cash_flow):.0f}€/month effort d'épargne"
        
        # Build verdict
        verdict = (
            f"{yield_verdict} yield ({yield_analysis.gross_yield:.1f}% gross, "
            f"{yield_analysis.net_yield:.1f}% net). Property {cf_verdict}."
        )
        
        # Recommendations
        if rent_is_estimated:
            recommendations.append(
                "⚠️ Rent is estimated - verify actual market rent before investing"
            )
        
        if property_type == PropertyBuildType.NEUF:
            recommendations.append(
                "✅ New build = reduced notary fees (~2.5% vs ~7.5%)"
            )
        
        if yield_analysis.gross_yield < 3:
            recommendations.append(
                "📉 Below-average yield - consider negotiating price or finding higher-rent property"
            )
        
        if cash_flow.monthly_cash_flow < -200:
            recommendations.append(
                f"💸 Significant monthly effort required ({abs(cash_flow.monthly_cash_flow):.0f}€) - "
                "consider larger down payment or longer loan term"
            )
        
        if cash_flow.rent_coverage_ratio >= 1.1:
            recommendations.append(
                f"🟢 Strong rent coverage ({cash_flow.rent_coverage_ratio:.2f}x) - good margin of safety"
            )
        
        if loan_comparison and loan_comparison.best_cash_flow:
            best = loan_comparison.best_cash_flow
            if best.monthly_cash_flow > cash_flow.monthly_cash_flow + 50:
                recommendations.append(
                    f"💡 Better scenario: {best.loan_duration_years}yr loan with "
                    f"{best.down_payment_percentage:.0f}% down "
                    f"(+{best.monthly_cash_flow:.0f}€/month)"
                )
        
        return verdict, recommendations
    
    def format_report(self, report: InvestmentReport) -> str:
        """Format complete investment report as readable text."""
        lines = [
            "",
            "╔" + "═" * 68 + "╗",
            "║" + "INVESTMENT ANALYSIS REPORT".center(68) + "║",
            "║" + f"({report.city} - {report.postal_code})".center(68) + "║",
            "╚" + "═" * 68 + "╝",
            "",
            "=" * 70,
            "📋 PROPERTY SUMMARY",
            "=" * 70,
            f"Purchase price: {report.purchase_price:,}€",
            f"Surface area: {report.surface_area}m²",
            f"Price per m²: {report.purchase_price / report.surface_area:,.0f}€/m²",
            f"Property type: {report.notary_fees.property_type.value.upper()}",
            "",
        ]
        
        # Notary fees summary
        lines.extend([
            "=" * 70,
            "📝 ACQUISITION COSTS",
            "=" * 70,
            f"Purchase price: {report.purchase_price:,}€",
            f"Notary fees: {report.notary_fees.total_fees:,}€ ({report.notary_fees.fee_percentage:.1f}%)",
            f"TOTAL TO PAY: {report.total_acquisition_cost:,}€",
            "",
        ])
        
        # Rental income
        lines.extend([
            "=" * 70,
            "🏠 RENTAL INCOME",
            "=" * 70,
            f"Monthly rent: {report.monthly_rent:,.0f}€" + 
            (" (estimated)" if report.rent_is_estimated else ""),
            f"Annual rent: {report.monthly_rent * 12:,.0f}€",
            f"Rent per m²: {report.monthly_rent / report.surface_area:.1f}€/m²",
            "",
        ])
        
        # Yields
        lines.extend([
            "=" * 70,
            "📊 YIELD ANALYSIS (Rendement)",
            "=" * 70,
            f"Gross Yield (Brut): {report.gross_yield:.2f}%",
            f"Net Yield (Net): {report.net_yield:.2f}%",
            f"Net-Net Yield (après impôts): {report.yield_analysis.net_net_yield:.2f}%",
            "",
            f"Assessment: {report.yield_analysis.yield_assessment}",
            "",
        ])
        
        # Cash flow
        lines.extend([
            "=" * 70,
            "💰 CASH FLOW (with 20% down, 20yr loan)",
            "=" * 70,
            f"Monthly mortgage: {report.cash_flow_default.monthly_mortgage:,.0f}€",
            f"Monthly expenses: {report.cash_flow_default.monthly_expenses:,.0f}€",
            f"Monthly income: {report.cash_flow_default.monthly_income:,.0f}€",
            "",
            f"NET CASH FLOW: {'+' if report.monthly_cash_flow >= 0 else ''}{report.monthly_cash_flow:,.0f}€/month",
            f"STATUS: {report.cash_flow_status}",
            "",
        ])
        
        # Loan comparison if available
        if report.loan_comparison:
            lines.extend([
                "=" * 70,
                "📈 LOAN SCENARIO COMPARISON",
                "=" * 70,
            ])
            
            # Header
            lines.append(f"{'Duration':<10} {'Down Pmt':<18} {'Monthly Loan':<14} {'Cash Flow':<14}")
            lines.append("-" * 60)
            
            # Show top 5 scenarios by cash flow
            sorted_scenarios = sorted(
                report.loan_comparison.scenarios,
                key=lambda x: x.monthly_cash_flow,
                reverse=True
            )[:5]
            
            for s in sorted_scenarios:
                cf_str = f"{'+' if s.monthly_cash_flow >= 0 else ''}{s.monthly_cash_flow:,.0f}€"
                lines.append(
                    f"{s.loan_duration_years:>2} years    "
                    f"{s.down_payment_percentage:>3.0f}% ({s.down_payment:>7,}€)   "
                    f"{s.total_monthly_loan_cost:>8,.0f}€      "
                    f"{cf_str:>10}"
                )
            
            lines.extend([
                "",
                f"💡 {report.loan_comparison.recommendation}",
                "",
            ])
        
        # Verdict and recommendations
        lines.extend([
            "=" * 70,
            "🎯 INVESTMENT VERDICT",
            "=" * 70,
            report.verdict,
            "",
        ])
        
        if report.recommendations:
            lines.append("RECOMMENDATIONS:")
            for rec in report.recommendations:
                lines.append(f"  • {rec}")
        
        lines.extend([
            "",
            "=" * 70,
        ])
        
        return "\n".join(lines)
    
    def format_compact(self, report: InvestmentReport) -> str:
        """Format a compact one-line summary for comparison tables."""
        cf_symbol = "🟢" if report.monthly_cash_flow > 0 else "🟡" if report.monthly_cash_flow > -50 else "🔴"
        
        return (
            f"Yield: {report.gross_yield:.1f}% (gross) / {report.net_yield:.1f}% (net) | "
            f"Cash Flow: {cf_symbol} {'+' if report.monthly_cash_flow >= 0 else ''}"
            f"{report.monthly_cash_flow:.0f}€/mo | "
            f"Total Cost: {report.total_acquisition_cost:,}€"
        )
